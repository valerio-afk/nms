from backend.config import ConfigMixin
from constants import SOCK_PATH
from cmdl import UserModChangeHomeDir, RemoteCommandLineTransaction
from importlib import import_module
import pwd
import socket

class AccessServicesMixin(ConfigMixin):

    def __init__(this,*args,**kwargs):
        super().__init__(*args, **kwargs)

        this._access_services = {}
        this._setup_access_services()

    def _setup_access_services(this):
        module = import_module("services")
        account = this._cfg.get("access",{}).get("account",{})


        for service,args in this._cfg.get("access",{}).get("services",{}).items():
            try:
                cls = getattr(module,f"{service.upper()}Service")
                arguments = args.copy()
                arguments.update(account)
                arguments['mountpoint'] = this.mountpoint
                this._access_services[service] = cls(**arguments)
            except AttributeError:
                ... #service not implemented yet

        this._access_services['ssh'].add_change_hook("username", this._sys_username_changed)
        this._access_services['ftp'].add_pre_start_hook(this._set_pwd)
        this._access_services['web'].add_change_hook("port", this._web_port_changed)
        this._access_services['web'].add_change_hook("credential", this._web_credentials_changed)
        this._access_services['web'].add_change_hook("authentication", this._web_authentication_changed)

    def _web_port_changed(this, service):
        d = this._cfg.get("access", {}).get("services", {}).get("web", {})
        d['port'] = service.get("port")
        this._cfg['access']['services']['web'] = d

        this.flush_config()

    def _web_credentials_changed(this, service):
        d = this._cfg.get("access", {}).get("services", {}).get("web", {})
        d['credential'] = service.get("credential")
        this._cfg['access']['services']['web'] = d

        this.flush_config()

    def _web_authentication_changed(this, service):
        d = this._cfg.get("access", {}).get("services", {}).get("web", {})
        d['authentication'] = service.get("authentication")
        this._cfg['access']['services']['web'] = d

        this.flush_config()


    def _sys_username_changed(this,service):
        old_username = this._cfg['access']['account']['username']
        new_username = service.get("username")
        this._cfg['access']['account']['username'] = new_username
        this.flush_config()

        smb = this._access_services.get("smb",None)
        smb.set("username",new_username)


        if ((smb is not None) and (smb.is_active)):
            smb.disable(old_username)

    def _set_pwd(this, *args, **kwargs):
        if (this.is_pool_configured()):
            mp = this.mountpoint
            username = this._cfg.get("access",{}).get("services").get("account",{}).get("username",None)

            if (username is not None):
                current_pwd = pwd.getpwnam(username).pw_dir

                if (current_pwd!=mp):
                    cmd = UserModChangeHomeDir(username,current_pwd,mp)

                    trans = RemoteCommandLineTransaction(
                        socket.AF_UNIX,
                        socket.SOCK_STREAM,
                        SOCK_PATH,
                        cmd
                    )
                    trans.run()

    @property
    def get_access_services(this):
        return  this._access_services

    def disable_all_access_services(this):
        for name, s in this._access_services.items():
            if s.is_active:
                try:
                    s.disable()
                except:
                    raise Exception(f"Unable to disable {name.upper()} service. Please disable it manually.")
