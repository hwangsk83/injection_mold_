/*---------------------------------------------------------------------------*\
  titanFoam v6.5 - KINEMATIC PIMPLE v7 (FPE-hardened, robust)
  p = kinematic [0 2 -2], pRefValue=100, U_init = (2.3 0 0)

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
#include "fvcReconstruct.H"
#include "fvmDdt.H"
#include "fvmDiv.H"
#include "fvmLaplacian.H"
#include "fvmSup.H"
#include "fvMatrix.H"
#include "adjustPhi.H"

using namespace Foam;

// ---- NaN/Inf clamp helper ----
inline scalar clampSafe(scalar x, scalar lo=1e-30, scalar hi=1e30)
{
    if (std::isnan(x) || std::isinf(x) || x < lo) return lo;
    if (x > hi) return hi;
    return x;
}

int main(int argc, char *argv[])
{
    #include "setRootCase.H"
    #include "createTime.H"
    #include "createMesh.H"
    #include "createFields.H"

    Info<< "titanFoam v6.5 - FPE-HARDENED PIMPLE" << nl << endl;

    bool vpSwitch = false;
    const scalar vpThreshold =
        transportProperties.lookupOrDefault<scalar>("vpThreshold", 0.99);

    scalar CoNum = 0.0;
    const bool adjTs = runTime.controlDict().lookupOrDefault<bool>("adjustTimeStep", false);
    const scalar maxCo = runTime.controlDict().lookupOrDefault<scalar>("maxCo", 0.5);
    const scalar maxDt = runTime.controlDict().lookupOrDefault<scalar>("maxDeltaT", 0.001);
    IOdictionary fvSolutionDict
    (
        IOobject
        (
            "fvSolution",
            runTime.system(),
            mesh,
            IOobject::MUST_READ_IF_MODIFIED,
            IOobject::NO_WRITE
        )
    );
    const dictionary& pimpleDict = fvSolutionDict.subDict("PIMPLE");
    const int nOuterCorr = pimpleDict.lookupOrDefault<int>("nOuterCorrectors", 3);
    const label pRefCell = 0;
    const scalar pRefValue = 100;

    while (runTime.loop())
    {
        // ---- FPE-safe flux ----
        phi = fvc::flux(U);
        scalarField& phiI = phi.primitiveFieldRef();
        forAll(phiI, fi) { phiI[fi] = clampSafe(phiI[fi], -1e8, 1e8); }

        const scalarField deltaCoeffs(mesh.surfaceInterpolation::deltaCoeffs().primitiveField());
        const scalarField magSf(mesh.magSf().primitiveField());

        CoNum = gMax(deltaCoeffs * mag(phiI) / max(magSf, 1e-30))
              * runTime.deltaTValue();
        CoNum = max(CoNum, 1e-30);

        if (adjTs)
        {
            scalar newDt = runTime.deltaTValue() * min(maxCo / max(CoNum, 1e-30), 1.1);
            newDt = max(newDt, 1e-10);
            newDt = min(newDt, maxDt);
            runTime.setDeltaT(newDt);
        }

        Info<< "Courant = " << CoNum << " | dt = " << runTime.deltaTValue() << endl;

        for (int oCorr = 0; oCorr < nOuterCorr; oCorr++)
        {
            // ---- Viscosity (Cross-WLF, FPE-hardened) ----
            const volTensorField gradU(fvc::grad(U));
            const volSymmTensorField S(symm(gradU));
            const volScalarField gammaDotSq(2.0*(S&&S));
            const volScalarField gammaDot
            (
                sqrt(max(gammaDotSq, dimensionedScalar("eps", dimless/sqr(dimTime), 1e-20)))
              + dimensionedScalar("small", dimless/dimTime, 1e-8)
            );

            forAll(mesh.cells(), celli)
            {
                const scalar Tv    = min(max(T[celli], 300.0), 600.0);
                const scalar Tstar = D2.value();
                const scalar A2eff = max(A2.value(), 1e-5);
                const scalar dT    = max(Tv - Tstar, 0.0);
                scalar exponent = -A1.value()*dT / max(A2eff + dT, 1e-10);
                exponent = min(max(exponent, -50.0), 50.0);
                scalar mu0 = D1.value() * Foam::exp(exponent);
                if (std::isnan(mu0) || std::isinf(mu0)) mu0 = 1e8;
                mu0 = max(mu0, 1e-3);
                const scalar crossArg = mu0 * clampSafe(gammaDot[celli]) / max(tau_star.value(), 1.0);
                scalar muPoly = mu0 / max(1.0 + Foam::pow(crossArg, 1.0-n_poly.value()), 1e-20);
                if (std::isnan(muPoly) || std::isinf(muPoly)) muPoly = 1e5;
                muPoly = min(max(muPoly, 10.0), 1e5);
                const scalar av = min(max(alpha[celli], 0.0), 1.0);
                mu[celli] = av*muPoly + (1.0-av)*max(muPoly, 10.0);
                mu[celli] = max(mu[celli], 10.0);
            }
            mu.correctBoundaryConditions();

            // ---- Alpha transport ----
            if (oCorr == 0)
            {
                fvScalarMatrix alphaEqn
                (
                    fvm::ddt(alpha) + fvm::div(phi, alpha, "div(phi,alpha)")
                );
                alphaEqn.solve();
                forAll(alpha, celli) { alpha[celli] = min(max(alpha[celli], 0.0), 1.0); }
                alpha.correctBoundaryConditions();
            }

            // ---- Momentum (kinematic, FPE-safe rAU) ----
            volScalarField nu("nu", mu/rho);
            fvVectorMatrix UEqn
            (
                fvm::ddt(U) + fvm::div(phi, U) - fvm::laplacian(nu, U)
            );
            UEqn.relax();
            if (vpSwitch)
            {
                UEqn += fvm::Sp(dimensionedScalar("vpDamp", dimless/dimTime, 50.0), U);
            }
            solve(UEqn == -fvc::grad(p));

            // ---- Pressure correction (ddtCorr ON, FPE-safe) ----
            volScalarField rAU("rAU", 1.0/UEqn.A());
            scalarField& rAUI = rAU.primitiveFieldRef();
            forAll(rAUI, celli) { rAUI[celli] = clampSafe(rAUI[celli], 0, 1e6); }

            const volVectorField HbyA("HbyA", rAU*UEqn.H());
            surfaceScalarField phiHbyA
            (
                "phiHbyA",
                fvc::flux(HbyA) + fvc::interpolate(rAU) * fvc::ddtCorr(U, phi)
            );
            adjustPhi(phiHbyA, U, p);
            fvScalarMatrix pEqn
            (
                fvm::laplacian(fvc::interpolate(rAU), p) == fvc::div(phiHbyA)
            );
            pEqn.setReference(pRefCell, pRefValue);
            pEqn.solve();
            phi = phiHbyA - pEqn.flux();
            // FPE-safe phi after flux correction
            forAll(phiI, fi) { phiI[fi] = clampSafe(phiI[fi], -1e8, 1e8); }
            U = HbyA - rAU * fvc::grad(p);
            forAll(U, celli)
            {
                for (int d=0; d<3; d++) { if (std::isnan(U[celli][d]) || std::isinf(U[celli][d])) U[celli][d] = 0; }
            }
            U.correctBoundaryConditions();
        }

        // ---- p safety (p >= 0, NaN-safe) ----
        forAll(p, celli)
        {
            if (std::isnan(p[celli]) || std::isinf(p[celli]) || p[celli] < 0) p[celli] = 0;
            if (p[celli] > 1e6) p[celli] = 1e6;
        }
        p.correctBoundaryConditions();

        // ---- Monitor ----
        const scalar totalVol  = gSum(mesh.V());
        const scalar filledVol = gSum(alpha.primitiveField()*mesh.V());
        const scalar fillFrac  = filledVol / max(totalVol, VSMALL);
        if (fillFrac >= vpThreshold && !vpSwitch)
        {
            vpSwitch = true;
            Info<< ">>> V/P SWITCH at " << fillFrac*100.0 << "%" << nl;
        }

        const scalar maxP   = gMax(p.primitiveField());
        const scalar avgVisc = gAverage(mu.primitiveField());
        const scalar pPhysMPa = maxP * 1000.0 / 1e6;

        Info<< "Time = " << runTime.name()
            << " | FilledRatio = " << fillFrac*100.0 << "%"
            << " | MaxP(MPa) = " << pPhysMPa
            << " | AvgViscosity = " << avgVisc
            << " | Courant = " << CoNum
            << nl << endl;

        runTime.write();
    }

    Info<< "End." << nl << endl;
    return 0;
}
