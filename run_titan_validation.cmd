@echo off
REM titanFoam Validation Runner v3.0
REM Cleans old results, decomposes, and runs 4-core parallel

REM Step 0: Load OpenFOAM 12 environment
call "d:\Program-Files\blueCFD-Core-2024\setvars_OF12.bat"

cd /d "d:\Open_code_project\injection_mold_flow\validation_test"

echo =========================================================
echo  titanFoam v3.0 - 4-Core Parallel Validation Run
echo  Mesh: 8000 cells | EndTime: 1.0s
echo =========================================================

REM Step 1: Clean up old parallel decomposition
echo.
echo [1/5] Cleaning old processor results...
rmdir /s /q processor0\1 2>nul
rmdir /s /q processor0\1* 2>nul  
rmdir /s /q processor0\2* 2>nul
rmdir /s /q processor0\3* 2>nul
rmdir /s /q processor0\0* 2>nul
rmdir /s /q processor1\1 2>nul
rmdir /s /q processor1\1* 2>nul
rmdir /s /q processor1\2* 2>nul
rmdir /s /q processor1\3* 2>nul
rmdir /s /q processor1\0* 2>nul
rmdir /s /q processor2\1 2>nul
rmdir /s /q processor2\1* 2>nul
rmdir /s /q processor2\2* 2>nul
rmdir /s /q processor2\3* 2>nul
rmdir /s /q processor2\0* 2>nul
rmdir /s /q processor3\1 2>nul
rmdir /s /q processor3\1* 2>nul
rmdir /s /q processor3\2* 2>nul
rmdir /s /q processor3\3* 2>nul
rmdir /s /q processor3\0* 2>nul
echo  Done.

REM Step 2: Re-decompose mesh
echo.
echo [2/5] Running decomposePar...
decomposePar -force > log.decomposePar 2>&1
if %errorlevel% neq 0 (
    type log.decomposePar
    echo [ERROR] decomposePar failed!
    pause
    exit /b %errorlevel%
)
echo  decomposePar OK.

REM Step 3: Run titanFoam parallel
echo.
echo [3/5] Running titanFoam (4-core parallel)...
echo  Estimated runtime: 5-30 minutes
echo  (monitor log.titanFoam for progress)
IF EXIST log.titanFoam del log.titanFoam
mpiexec -np 4 titanFoam.exe -parallel > log.titanFoam 2>&1
if %errorlevel% neq 0 (
    echo [WARN] titanFoam exited with code %errorlevel%
    echo  Check log.titanFoam for details
)

REM Step 4: Reconstruct (if needed)
echo.
echo [4/5] Reconstructing parallel results...
reconstructPar > log.reconstructPar 2>&1

REM Step 5: Parse results
echo.
echo [5/5] Parsing results...
python d:\Open_code_project\injection_mold_flow\parse_results.py

echo.
echo =========================================================
echo  Validation Run Complete!
echo  Check solver_monitor.csv for detailed data
echo =========================================================
pause
