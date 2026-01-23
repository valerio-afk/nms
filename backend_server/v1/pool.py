from fastapi import HTTPException, APIRouter
from backend_server.utils.config import CONFIG
from pydantic import BaseModel
from typing import Any, Optional, List
from backend_server.utils.cmdl import CommandLine, ZFSLoadKey, ZFSMount, LocalCommandLineTransaction, ZFSUnmount, ZFSUnLoadKey, ZFSDestroy, ZFSCreate

pool = APIRouter(
    prefix='/pool',
    tags=['pool'],
#    dependencies=[Depends(verify_token_factory())]
)

class PoolProperty(BaseModel):
    property:str
    value: Any

class DiskArrayNotConfigured(RuntimeError):
    def __init__(this):
        super().__init__("Disk array not configured")


def unmount():
    if (not CONFIG.is_pool_configured):
        raise DiskArrayNotConfigured()

    if (not CONFIG.is_mounted):
        return

    #TODO: disable all access services

    cmds: List[CommandLine] = [
        ZFSUnmount(CONFIG.pool_name, CONFIG.dataset_name),
        ZFSUnmount(CONFIG.pool_name)
    ]

    if (CONFIG.has_encryption):
        cmds.append(ZFSUnLoadKey(CONFIG.pool_name))


    trans = LocalCommandLineTransaction(*cmds)

    output = trans.run()

    if (not trans.success):
        error = "\n".join([o['stderr'] for o in output])
        raise RuntimeError(f"Unable to unmount disk array: {error}")

@pool.get("/get/{prop}",
          response_model=PoolProperty,
          responses={
              500: {"description": "Any internal error to retrieve pool information"},
              404: {"description": "Invalid pool property"},
            },
          summary="Get a configuration/status pool property"
          )
def pool_get_property(prop:str) -> Optional[PoolProperty]:
    try:
        match prop:
            case "dataset_name":
                return PoolProperty(property=prop,value=CONFIG.dataset_name)
            case "mountpoint":
                return PoolProperty(property=prop, value=CONFIG.mountpoint)
            case "is_mounted":
                return PoolProperty(property=prop, value=CONFIG.is_mounted)
            case "is_configured":
                return PoolProperty(property=prop, value=CONFIG.is_pool_configured)
            case "is_present":
                return PoolProperty(property=prop, value=CONFIG.is_pool_present)
            case "pool_capacity":
                return PoolProperty(property=prop, value=CONFIG.get_pool_capacity)
            case _:
                CONFIG.error(f"Requested invalid pool property {prop}")
                raise HTTPException(status_code=404, detail=f"Property {prop} not valid for pool")
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

@pool.post(
    "/mount",
    responses={500: {"description": "Missing configuration/Other internal errors"}},
    summary="Mount the disk array"
)
def pool_mount() -> None:
    if (not CONFIG.is_pool_configured):
        raise HTTPException(status_code=500, detail="Disk array not configured")

    if (CONFIG.is_mounted):
        return

    cmds = []

    if (CONFIG.has_encryption):
        cmds.append(ZFSLoadKey(CONFIG.pool_name, CONFIG.key_filename))

    cmds.append(ZFSMount(CONFIG.pool_name))
    cmds.append(ZFSMount(CONFIG.pool_name, CONFIG.dataset_name))

    trans = LocalCommandLineTransaction(*cmds)

    output = trans.run()

    if (not trans.success):
        error = "\n".join([o['stderr'] for o in output])
        raise HTTPException(status_code=500, detail=f"Unable to mount disk array: {error}")

@pool.post(
    "/unmount",
    responses={500: {"description": "Missing configuration/Other internal errors"}},
    summary="Unmount the disk array"
)
def pool_unmount() -> None:
    try:
        unmount()
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

@pool.post(
    "/format",
    responses={500: {"description": "Any internal errors"}},
    summary="Destroy and recreate a new disk array"
)
def pool_format() -> None:
    try:
        if (not CONFIG.is_pool_configured):
            raise DiskArrayNotConfigured()

        # TODO: disable all access services

        unmount()

        pool = CONFIG.pool_name
        dataset = CONFIG.dataset_name

        commands = [
            ZFSDestroy(pool, dataset),
            ZFSCreate(pool, dataset)
        ]

        trans = LocalCommandLineTransaction(*commands)

        output = trans.run()

        if (not trans.success):
            errors = "\n ".join([x["stderr"] for x in output])
            raise RuntimeError(errors)

    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))