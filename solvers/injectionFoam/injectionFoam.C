/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM 12 Compatible Injection Molding Solver
   \\    /   O peration     | injectionFoam: Cross-WLF + Modified Tait PVT
    \\  /    A nd           |
     \\/     M anipulation  |
-------------------------------------------------------------------------------
Description
    Transient solver for injection molding simulation:
    - Cross-WLF Non-Newtonian viscosity model
    - Modified Tait Equation of State (PVT)
    - Volume fraction tracking (alpha) with V/P switchover

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
\*---------------------------------------------------------------------------*/

#include "argList.H"
#include "Time.H"
#include "fvMesh.H"
#include "volFields.H"
#include "surfaceFields.H"
#include "IOdictionary.H"
#include "fvcGrad.H"
#include "fvcDdt.H"
#include "fvcDiv.H"
#include "fvcFlux.H"
#include "fvcSnGrad.H"
#include "fvcSurfaceIntegrate.H"
#include "fvmDdt.H"
#include "fvmDiv.H"
#include "fvmLaplacian.H"
#include "fvmSup.H"
#include "fvMatrix.H"
#include "mixedFvPatchFields.H"

using namespace Foam;

// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

int main(int argc, char *argv[])
{
    #include "setRootCase.H"
    #include "createTime.H"
    #include "createMesh.H"
    #include "createFields.H"

    Info<< "\n==========================================" << nl
        << "  injectionFoam v1.0 - OpenFOAM 12" << nl
        << "  Non-Newtonian Cross-WLF + Tait PVT" << nl
        << "==========================================" << nl << endl;

    // V/P Switchover state
    bool   vpSwitch   = false;
    const scalar vpThreshold = transportProperties.lookupOrDefault<scalar>("vpThreshold", 0.98);

    // =========================================================================
    while (runTime.loop())
    {
        // ------------------------------------------------------------------
        // 1. Cross-WLF Viscosity (Polymer Phase) and mixing with Air
        //    mu_0 = D1 * exp(-A1*(T-T*)/(A2+(T-T*)))
        //    mu   = alpha * mu_polymer + (1 - alpha) * mu_air
        // ------------------------------------------------------------------
        {
            const volTensorField  gradU(fvc::grad(U));
            const volSymmTensorField S(symm(gradU));
            const volScalarField gammaDotSq(2.0*(S&&S));

            const scalar n_poly = 0.3;
            const scalar mu_air = 1.8e-5; // Air viscosity (Pa*s)

            forAll(mesh.cells(), celli)
            {
                const scalar pVal   = max(p[celli], 0.0);
                const scalar TVal   = T[celli];
                const scalar T_star = D2.value() + D3.value()*pVal;
                const scalar A2_eff = max(A2.value() + D3.value()*pVal, 1e-5);
                const scalar dT     = max(TVal - T_star, 0.0); // Prevent negative dT and blow-up

                scalar mu_0 = D1.value()
                    * Foam::exp(-A1.value()*dT / (A2_eff + dT + 1e-8));
                mu_0 = min(max(mu_0, 1e-5), 1e5); // Clamp mu_0 to a max of 1e5 Pa*s

                const scalar tau_star = max(b3m.value(), 1e5);
                const scalar gammaVal =
                    Foam::sqrt(max(gammaDotSq[celli], 0.0)) + 1e-8;

                const scalar mu_poly = min(
                    mu_0 / (1.0 + Foam::pow(mu_0*gammaVal/tau_star, 1.0 - n_poly)),
                    1e5 // Clamp polymer viscosity
                );

                // Multi-phase Viscosity Mixing
                const scalar alphaVal = min(max(alpha[celli], 0.0), 1.0);
                mu[celli] = alphaVal * mu_poly + (1.0 - alphaVal) * mu_air;
            }
            mu.correctBoundaryConditions();
        }

        // ------------------------------------------------------------------
        // 2. Modified Tait Equation of State (Polymer Phase) and mixing with Air
        //    v0 = b1m + b2m*(T - b5)
        //    B  = b3m*exp(-b4m*(T - b5))
        //    v  = v0*(1 - C*ln(1 + p/B))
        //    rho = alpha * rho_polymer + (1 - alpha) * rho_air
        // ------------------------------------------------------------------
        {
            const scalar rho_air = 1.2; // Air density (kg/m^3)

            forAll(mesh.cells(), celli)
            {
                const scalar TVal = T[celli];
                const scalar pVal = max(p[celli], 0.0);

                scalar v0 = b1m.value() + b2m.value()*(TVal - b5.value());
                v0 = max(v0, 1e-4);

                const scalar B  = max(
                    b3m.value()*Foam::exp(-b4m.value()*(TVal - b5.value())),
                    1.0);
                const scalar Cv = (C_tait.value() > 0.0)
                    ? C_tait.value() : 0.0894;

                // Protect the logarithm against negative/zero arguments
                const scalar logArg = max(1.0 + pVal/B, 1e-5);
                const scalar v = max(v0*(1.0 - Cv*Foam::log(logArg)), 1e-5);
                const scalar rho_poly = max(1.0/v, 500.0); // Clamp polymer density to physical minimum of 500 kg/m^3

                // Multi-phase Density Mixing
                const scalar alphaVal = min(max(alpha[celli], 0.0), 1.0);
                rho[celli] = alphaVal * rho_poly + (1.0 - alphaVal) * rho_air;
            }
            rho.correctBoundaryConditions();
        }

        // ------------------------------------------------------------------
        // 3. Alpha (VOF fill) transport:  d(alpha)/dt + div(U*alpha) = 0
        // ------------------------------------------------------------------
        {
            fvScalarMatrix alphaEqn
            (
                fvm::ddt(alpha)
              + fvm::div(phi, alpha)
            );
            alphaEqn.solve();
            
            // Defensive check and strict bounding for alpha
            forAll(alpha, celli)
            {
                if (std::isnan(alpha[celli]))
                {
                    alpha[celli] = 0.0;
                }
                alpha[celli] = min(max(alpha[celli], 0.0), 1.0);
            }
            alpha.correctBoundaryConditions();
        }

        // Final defensive check against NaNs in mixed rho and mu fields
        forAll(mesh.cells(), celli)
        {
            if (std::isnan(rho[celli])) rho[celli] = 1.2;
            if (std::isnan(mu[celli]))  mu[celli]  = 1.8e-5;
        }
        rho.correctBoundaryConditions();
        mu.correctBoundaryConditions();

        // ------------------------------------------------------------------
        // 4. Momentum equation (Kinematic/Acceleration form)
        // ------------------------------------------------------------------
        volScalarField nu("nu", mu/rho);

        fvVectorMatrix UEqn
        (
            fvm::ddt(U)
          + fvm::div(phi, U)
          - fvm::laplacian(nu, U)
        );

        UEqn.relax(); // Activate matrix relaxation from fvSolution

        if (vpSwitch)
        {
            // Packing phase: damp velocity via implicit source term
            UEqn += fvm::Sp(
                dimensionedScalar("vpDamp", dimensionSet(0, 0, -1, 0, 0, 0, 0), 20.0), U);
        }

        SolverPerformance<vector> solveRes = solve(UEqn == -fvc::grad(p)/rho);

        // ------------------------------------------------------------------
        // 5. Pressure correction (SIMPLE-like, scaled by rho)
        // ------------------------------------------------------------------
        {
            const volScalarField rAU("rAU", 1.0/max(UEqn.A(), dimensionedScalar("smallA", dimensionSet(0, 0, -1, 0, 0, 0, 0), 1e-12)));
            const volScalarField rAUpRho("rAUpRho", rAU/max(rho, dimensionedScalar("rhoLimit", rho.dimensions(), 100.0)));
            const volVectorField HbyA("HbyA", rAU*UEqn.H());
            surfaceScalarField phiHbyA("phiHbyA", fvc::flux(HbyA));

            fvScalarMatrix pEqn
            (
                fvm::laplacian(rAUpRho, p) == fvc::div(phiHbyA)
            );
            pEqn.solve();

            phi = phiHbyA - pEqn.flux();
            
            // Clamping surface flux phi to physical max velocity of 5.0 m/s
            const surfaceScalarField magSf(mesh.magSf());
            forAll(phi, facei)
            {
                phi[facei] = min(max(phi[facei], -5.0*magSf[facei]), 5.0*magSf[facei]);
            }

            U   = HbyA - rAUpRho*fvc::grad(p);
            
            // Clamping velocity U to physical max velocity of 5.0 m/s
            forAll(U, celli)
            {
                for (direction d=0; d<3; ++d)
                {
                    U[celli][d] = min(max(U[celli][d], -5.0), 5.0);
                }
            }
            U.correctBoundaryConditions();

            // Clamping pressure p to physical range of 0 ~ 100 MPa (1e8 Pa) to support 80 MPa packing
            forAll(p, celli)
            {
                p[celli] = min(max(p[celli], 0.0), 1e8);
            }
            p.correctBoundaryConditions();
        }

        // ------------------------------------------------------------------
        // 5. Solve Temperature (Energy) Equation with Viscous Dissipation
        // ------------------------------------------------------------------
        {
            // Explicitly define physical properties for polymer and air phases
            // diffusivity alpha_T (m2/s): poly ~ 7.5e-8, air ~ 2.16e-5
            dimensionedScalar alpha_T_poly("alpha_T_poly", dimensionSet(0, 2, -1, 0, 0, 0, 0), 7.5e-8);
            dimensionedScalar alpha_T_air("alpha_T_air", dimensionSet(0, 2, -1, 0, 0, 0, 0), 2.16e-5);
            volScalarField alpha_T("alpha_T", alpha*alpha_T_poly + (1.0 - alpha)*alpha_T_air);

            // volumetric heat capacity rhoCp (J/m3K): poly ~ 2e6, air ~ 1.2e3
            dimensionedScalar rhoCp_poly("rhoCp_poly", dimensionSet(1, -1, -2, -1, 0, 0, 0), 2.0e6);
            dimensionedScalar rhoCp_air("rhoCp_air", dimensionSet(1, -1, -2, -1, 0, 0, 0), 1.2e3);
            volScalarField rhoCp("rhoCp", alpha*rhoCp_poly + (1.0 - alpha)*rhoCp_air);

            // Viscous shear heating: S_visc_Cp = mu * gammaDotSq / rhoCp
            const volTensorField gradU(fvc::grad(U));
            const volSymmTensorField S(symm(gradU));
            const volScalarField gammaDotSq(2.0*(S&&S));
            volScalarField S_visc_Cp("S_visc_Cp", mu*gammaDotSq/rhoCp);

            fvScalarMatrix TEqn
            (
                fvm::ddt(T)
              + fvm::div(phi, T)
              - fvm::laplacian(alpha_T, T)
             ==
                S_visc_Cp
            );
            TEqn.solve();
            
            // Temperature safety clamp (250 K - 650 K)
            forAll(T, celli)
            {
                T[celli] = min(max(T[celli], 250.0), 650.0);
            }
            T.correctBoundaryConditions();
        }

        // ------------------------------------------------------------------
        // 6. V/P Switchover logic
        // ------------------------------------------------------------------
        const scalar totalVol  = gSum(mesh.V());
        const scalar filledVol = gSum(alpha.primitiveField()*mesh.V());
        const scalar fillFrac  = filledVol / (totalVol + SMALL);

        if (fillFrac >= vpThreshold && !vpSwitch)
        {
            vpSwitch = true;
            Info<< "  [V/P SWITCH] C++ Runtime Switch triggered at " << fillFrac*100.0 << "%" << endl;

            // Dynamically change boundary conditions at the gate_inlet patch!
            const label gateInletPatchID = mesh.boundaryMesh().findPatchID("gate_inlet");
            if (gateInletPatchID != -1)
            {
                // 1. U boundary: set gate_inlet velocity values to zero
                U.boundaryFieldRef()[gateInletPatchID] == vector(0, 0, 0);

                // 2. p boundary: cast to mixedFvPatchScalarField, set valueFraction to 1.0 (fixedValue), and refValue to 80 MPa (8e7 Pa)
                mixedFvPatchScalarField& pPatch = refCast<mixedFvPatchScalarField>(p.boundaryFieldRef()[gateInletPatchID]);
                pPatch.valueFraction() == 1.0;
                pPatch.refValue() == 8.0e7;
            }
        }

        // ------------------------------------------------------------------
        // 7. Convergence log (Streamlit parsing format)
        // ------------------------------------------------------------------
        // Retrieve true initial residual from solver performance (x-component magnitude)
        const scalar resU = solveRes.initialResidual().x();

        Info<< "Time = " << runTime.name()
            << " | residuals: Ux_init = " << resU
            << " | FilledRatio = "        << fillFrac*100.0 << "%"
            << nl << endl;

        runTime.write();
    }

    Info<< "End of injectionFoam simulation." << nl << endl;
    return 0;
}

// ************************************************************************* //
