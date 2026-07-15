// createFields.H - injectionFoam OpenFOAM 12 Foundation
// Inline include file - no header guards needed

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
// Use readScalar(dict.lookup()) for OpenFOAM Foundation 12
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
    dimensionedScalar("mu0", dimensionSet(1, -1, -1, 0, 0, 0, 0), 1.0)
);
