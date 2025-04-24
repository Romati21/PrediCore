{ pkgs ? import <nixpkgs> {} }:

let
  pypng = pkgs.python3Packages.buildPythonPackage rec {
    pname = "pypng";
    version = "0.20220715.0";
    format = "pyproject";
    src = pkgs.fetchPypi {
      inherit pname version;
      hash = "sha256-c5xDO6lvB4MV3lTA25da7lN8vD4dCuTtmqsMoeQn4sE=";
    };
    nativeBuildInputs = with pkgs.python3Packages; [ setuptools ];
    doCheck = false;
  };

  pyqrcode = pkgs.python3Packages.buildPythonPackage rec {
    pname = "PyQRCode";
    version = "1.2.1";
    format = "setuptools";
    src = pkgs.fetchPypi {
      inherit pname version;
      hash = "sha256-/b92NHM+VrcuJ/m85G5FULdaOixCBBQDXK6dnSayNNU=";
    };
    doCheck = false;
  };

  pythonEnv = pkgs.python3.withPackages (ps: with ps; [
    alembic
    annotated-types
    anyio
    asyncpg
    certifi
    click
    databases
    dnspython
    email-validator
    fastapi
    fastapi-cli
    greenlet
    h11
    httpcore
    httptools
    httpx
    idna
    jinja2
    mako
    markdown-it-py
    markupsafe
    mdurl
    orjson
    pillow
    psycopg2
    pydantic
    pygments
    pypng
    pyqrcode
    python-dotenv
    python-multipart
    pyyaml
    qrcode
    rich
    shellingham
    sniffio
    sqlalchemy
    starlette
    typer
    typing-extensions
    ujson
    uvicorn
    uvloop
    watchfiles
    websockets
    apscheduler
    aiofiles
  ]);
in

pkgs.mkShell {
  buildInputs = [
    pythonEnv
    pkgs.postgresql
    pkgs.python3Packages.pip # Добавляем pip
  ];
  shellHook = ''
    export PYTHONPATH=$PWD:$PYTHONPATH
    echo "Python environment ready. Run 'uvicorn app.main:app --host 0.0.0.0 --port 8000' to start."
    echo "To generate requirements.txt, run 'pip list --format=freeze > requirements.txt'"
  '';
}
