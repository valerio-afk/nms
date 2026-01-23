from fastapi import APIRouter, Depends
from backend_server.v1.auth import verify_token_factory
from backend_server.utils.cmdl import Shutdown,Reboot

acpi = APIRouter(prefix='/acpi',tags=['acpi'],dependencies=[Depends(verify_token_factory())])

@acpi.post('/shutdown',summary="Power-off the NAS")
def shutdown():
    Shutdown().execute()


@acpi.post('/restart',summary="Reboots the NAS")
def restart():
    Reboot().execute()

