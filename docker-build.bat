@echo off
echo Building and starting the Medical Travel Matcher in Docker...
docker-compose up --build -d
echo.
echo =======================================================
echo App is starting! The first time might take a few minutes.
echo.
echo Once running, the Interactive Tester will be available at:
echo http://localhost:8000/tester
echo =======================================================
echo.
pause
