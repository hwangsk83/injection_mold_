// createFields.H - titanFoam Field Declarations and Dictionary Maps
// Inline include file - no header guards needed
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

Info<< "Reading field p\n" << endl;
volScalarField p
(
    IOobject
    (
        "p",
        runTime.name(),
        mesh,
        IOobject::MUST_READ,
        IOobject::AUTO_WRITE
    ),
    mesh
);

Info<< "Reading field U\n" << endl;
volVectorField U
(
    IOobject
    (
        "U",
        runTime.name(),
        mesh,
        IOobject::MUST_READ,
        IOobject::AUTO_WRITE
    ),
    mesh
);

Info<< "Reading field T (Temperature)\n" << endl;
volScalarField T
(
    IOobject
    (
        "T",
        runTime.name(),
        mesh,
        IOobject::MUST_READ,
        IOobject::AUTO_WRITE
    ),
    mesh
);

Info<< "Reading field alpha (Volume Fraction)\n" << endl;
volScalarField alpha
(
    IOobject
    (
        "alpha",
        runTime.name(),
        mesh,
        IOobject::MUST_READ,
        IOobject::AUTO_WRITE
    ),
    mesh
);

#include "createPhi.H"

Info<< "Reading transportProperties\n" << endl;
IOdictionary transportProperties
(
    IOobject
    (
        "transportProperties",
        runTime.constant(),
        mesh,
        IOobject::MUST_READ,
        IOobject::NO_WRITE
    )
);

// Cross-WLF viscosity model coefficients
const dictionary& wlfCoeffs = transportProperties.subDict("CrossWLFCoeffs");

dimensionedScalar D1
(
    "D1",
    dimensionSet(1, -1, -1, 0, 0, 0, 0),
    readScalar(wlfCoeffs.lookup("D1"))
);
dimensionedScalar D2
(
    "D2",
    dimensionSet(0, 0, 0, 1, 0, 0, 0),
    readScalar(wlfCoeffs.lookup("D2"))
);
dimensionedScalar D3
(
    "D3",
    dimensionSet(0, 2, 2, 1, 0, 0, 0),
    readScalar(wlfCoeffs.lookup("D3"))
);
dimensionedScalar A1
(
    "A1",
    dimless,
    readScalar(wlfCoeffs.lookup("A1"))
);
dimensionedScalar A2
(
    "A2",
    dimensionSet(0, 0, 0, 1, 0, 0, 0),
    readScalar(wlfCoeffs.lookup("A2"))
);

// Cross model parameters
dimensionedScalar tau_star
(
    "tau_star",
    dimensionSet(1, -1, -2, 0, 0, 0, 0),
    wlfCoeffs.lookupOrDefault<scalar>("tau_star", 1.2e5)
);
dimensionedScalar n_poly
(
    "n_poly",
    dimless,
    wlfCoeffs.lookupOrDefault<scalar>("n_poly", 0.3)
);

// Modified Tait PVT model coefficients
const dictionary& taitCoeffs = transportProperties.subDict("TaitCoeffs");

dimensionedScalar b1m
(
    "b1m",
    dimensionSet(-1, 3, 0, 0, 0, 0, 0),
    readScalar(taitCoeffs.lookup("b1m"))
);
dimensionedScalar b2m
(
    "b2m",
    dimensionSet(-1, 3, 0, -1, 0, 0, 0),
    readScalar(taitCoeffs.lookup("b2m"))
);
dimensionedScalar b3m
(
    "b3m",
    dimensionSet(1, -1, -2, 0, 0, 0, 0),
    readScalar(taitCoeffs.lookup("b3m"))
);
dimensionedScalar b4m
(
    "b4m",
    dimensionSet(0, 0, 0, -1, 0, 0, 0),
    readScalar(taitCoeffs.lookup("b4m"))
);
dimensionedScalar b5
(
    "b5",
    dimensionSet(0, 0, 0, 1, 0, 0, 0),
    readScalar(taitCoeffs.lookup("b5"))
);
dimensionedScalar C_tait
(
    "C_tait",
    dimless,
    readScalar(taitCoeffs.lookup("C_tait"))
);

// Non-isothermal energy equation coefficients (Commercial standard)
Info<< "Reading thermal properties\n" << endl;
dimensionedScalar Cp_poly
(
    "Cp_poly",
    dimensionSet(0, 2, -2, -1, 0, 0, 0),
    transportProperties.lookupOrDefault<scalar>("Cp_poly", 2000.0)
);
dimensionedScalar Cp_air
(
    "Cp_air",
    dimensionSet(0, 2, -2, -1, 0, 0, 0),
    transportProperties.lookupOrDefault<scalar>("Cp_air", 1000.0)
);
dimensionedScalar k_poly
(
    "k_poly",
    dimensionSet(1, 1, -3, -1, 0, 0, 0),
    transportProperties.lookupOrDefault<scalar>("k_poly", 0.15)
);
dimensionedScalar k_air
(
    "k_air",
    dimensionSet(1, 1, -3, -1, 0, 0, 0),
    transportProperties.lookupOrDefault<scalar>("k_air", 0.026)
);

// Computed fields
Info<< "Creating density field rho\n" << endl;
volScalarField rho
(
    IOobject
    (
        "rho",
        runTime.name(),
        mesh,
        IOobject::NO_READ,
        IOobject::AUTO_WRITE
    ),
    mesh,
    dimensionedScalar("rho0", dimensionSet(1, -3, 0, 0, 0, 0, 0), 1000.0)
);

Info<< "Creating viscosity field mu\n" << endl;
volScalarField mu
(
    IOobject
    (
        "mu",
        runTime.name(),
        mesh,
        IOobject::NO_READ,
        IOobject::AUTO_WRITE
    ),
    mesh,
    // Initial mu = Cross-WLF at T=503.15K, p=1e5Pa: ~1032 Pa·s (polymer melt)
    dimensionedScalar("mu0", dimensionSet(1, -1, -1, 0, 0, 0, 0), 1000.0)
);

// Mixed Thermal properties fields for energy solver
Info<< "Creating thermal properties fields Cp and k\n" << endl;
volScalarField Cp
(
    IOobject
    (
        "Cp",
        runTime.name(),
        mesh,
        IOobject::NO_READ,
        IOobject::NO_WRITE
    ),
    mesh,
    Cp_air
);

volScalarField k
(
    IOobject
    (
        "k",
        runTime.name(),
        mesh,
        IOobject::NO_READ,
        IOobject::NO_WRITE
    ),
    mesh,
    k_air
);

