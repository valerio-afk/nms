export interface ErrorDetail {
    type?: string;
    code: string;
    params?: (string | number)[] | null;
}

export const ERROR_MESSAGES_EN: Record<string, string> = {
    // General
    E_UNKNOWN: "Unknown Error",
    E_UNKNOWN_RESPONSE: "Unknown response from server",
    E_PROPERTY: "Error while getting %(prop)s: %(info)s",
    E_CSRF: "Form validation failed",
    E_UNKNOWN_METHOD: "Unknown operation.",
    E_READ_FILE: "Unable to read the file %(file)s: %(info)s",
    E_REL_PATH: "Path `%(path1)s` is not relative to `%(path2)s`",
    E_SELINUX_PORT: "Error while obtaining system information on ports: %(info)s",
    E_SYSTEMD_START: "Error while starting the system service(s) %(services)s: %(info)s",
    E_SYSTEMD_STOP: "Error while stopping the system service(s) %(services)s: %(info)s",
    E_SYSTEMD_RESTART: "Error while restarting system service(s) %(services)s: %(info)s",
    E_TOO_MANY_REQ: "Too many requests. Please wait one minute.",
    E_INVALID_VALUE: "Invalid value for %(prop)s: %(val)s",
    E_NO_PERM: "You do not have permission to perform this action.",

    // Auth
    E_AUTH_ALREADY_CONFIG: "You have already an OTP credentials configured.",
    E_AUTH_INVALID: "Invalid authorisation.",
    E_AUTH_EXPIRED: "Authorisation token expired.",
    E_AUTH_REVOKED: "Authorisation token revoked.",
    E_AUTH_MALFORMED: "Authorisation token malformed.",
    E_AUTH_NOT_CONF: "OTP secret not configured yet.",
    E_AUTH_WRONG_OTP: "Invalid OTP.",

    // Storage Pool
    E_POOL_ALREADY_CONF: "The disk array is already configured.",
    E_POOL_NO_CONF: "Disk array not configured yet.",
    E_POOL_CONFIG: "Disk array is configured.",
    E_POOL_DISK_UNAVAL: "Disk %(dev)s is not available to be in the new disk array.",
    E_POOL_NEW: "Unable to create a new disk array: %(info)s",
    E_POOL_DESTROY: "Unable to destroy the disk array: %(info)s",
    E_POOL_REDUNDANCY_MIN: "You must have at least 3 disks connected to opt in redundancy.",
    E_POOL_EXPAND: "Error while adding %(dev)s: %(info)s",
    E_POOL_EXPAND_INFO: "Could not retrieve information for the disk: %(dev)s",
    E_POOL_EXPAND_STATUS: "Unable to get array expansion status: %(info)s",
    E_POOL_KEY: "Error while retrieving the encryption key: %(info)s",
    E_POOL_KEY_IMPORT: "Error while importing the encryption key: %(info)s",
    E_POOL_ATTACH: "Error while attaching an existing pool: %(info)s",
    E_POOL_LIST: "Unable to retrieve the list of pools.",
    E_POOL_RECOVERY: "Error while recovering the disk array: %(info)s",
    E_POOL_DISKS: "Error while retrieving the disks in the array: %(info)s",
    E_POOL_DISK_REPLACE: "Unable to replace %(dev1)s with %(dev2)s: %(info)s",
    E_POOL_DETACH: "Error while detaching the disk array: %(info)s",
    E_POOL_MOUNT: "Error while mounting the disk array: %(info)s",
    E_POOL_UNMOUNT: "Error while unmounting the disk array: %(info)s",
    E_POOL_MOUNTED: "Disk array is mounted.",
    E_POOL_UNMOUNTED: "Disk array is unmounted.",
    E_POOL_SCRUB: "Error while verifying the disk array: %(info)s.",
    E_POOL_INVALID_MOUNTPOINT: "The provided mount point is not valid.",
    E_POOL_MOUNT_STATUS: "Error while retrieving the mount information the disk array: %(info)s",
    E_POOL_MOUNTPOINT: "Error while retrieving the mount point: %(info)s",
    E_POOL_RM_MOUNTPOINT: "Error while removing the mount point: %(info)s",
    E_POOL_FORMAT: "Error while formatting the disk array: %(info)s",
    E_POOL_CAPACITY: "Unable to read disk array capacity information: %(info)s",
    E_POOL_OPENED: "One or more disks cannot be opened. Your disk array CANNOT be used in this state.",
    E_POOL_DISK_MISSING: "One or more disks seems missing. Your disk array CANNOT be used in this state.",
    E_POOL_CORRUPTED: "The information related your disk array are corrupted. Recovery may be possible.",
    E_POOL_OUTDATED: "Your disk array seems to be outdated and cannot be used anymore.",
    E_POOL_SNAPSHOT_NAME: "Snapshot name `%(name)s` is invalid.",
    E_POOL_SNAPSHOT_CREATE: "Error while creating a new snapshot of your disk array: %(info)s",
    E_POOL_SNAPSHOT_DELETE: "Error while deleting the snapshot `%(name)s` from your disk array: %(info)s",
    E_POOL_SNAPSHOTS: "Error while retrieving the list of snapshots: %(info)s",
    E_POOL_SNAPSHOT_ROLLBACK: "Error while rolling back to `%(name)s`: %(info)s",

    // Disks
    E_DISK_ATTACH: "Unable to attach new device to disk array: %(details)s",
    E_DISK_FORMAT: "Error while formatting %(dev)s: %(info)s",
    E_DISK_SELF_TEST: "Error while running a self-test on %(dev)s: %(info)s",

    // Access Services
    E_ACCESS_ENABLED: "Error while enabling %(service)s: %(info)s",
    E_ACCESS_DISABLED: "Error while disabling %(service)s: %(info)s",
    E_ACCESS_DISABLING: "Unable to disable %(service)s. Please, disable it manually.",
    E_ACCESS_SERV_UNK: "Access service %(service)s not recognised.",
    E_ACCESS_PROP: "Error while changing the property `%(prop)s`: %(info)s",

    // Network
    E_NET_CHANGE_STATE: "Error while changing the state of the network interface %(iface)s: %(info)s",
    E_NET_CONNECTION_STATUS: "Error while retrieving the connection status for %(iface)s: %(info)s",
    E_NET_INVALID_NETMASK: "Invalid subnet mask",
    E_NET_INVALID_IP_ADDRESS: "Invalid IP address",
    E_NET_INVALID_GATEWAY: "Invalid gateway",
    E_NET_INVALID_DNS: "Invalid DNS address(es)",
    E_NET_WIFI_LIST: "Error while retrieving the list of WiFi networks for %(iface)s: %(info)s",
    E_NET_WIFI_CONNECT: "Unable to connect to `%(ssid)s`: %(info)s",
    E_NET_WIFI_DEV: "No valid WiFi network interfaces detected.",
    E_NET_AP: "Unable to create hotspot on %(iface)s: %(info)s",
    E_NET_VPN_NOTCONF: "VPN service not configured.",
    E_NET_VPN_STATE: "Unable to get the state of the VPN service: %(info)s",
    E_NET_VPN_KEY: "Error while retrieving the VPN key: %(info)s",
    E_NET_VPN_GEN_PRIVATE: "Error occurred while generating the private key: %(info)s",
    E_NET_VPN_GEN_PUBLIC: "Error occurred while generating the public key: %(info)s",
    E_NET_VPN_CONF: "Error occurred while reading the VPN configuration file: %(info)s",
    E_NET_VPN_USER: "VPN device `%(user)s` not found.",
    E_NET_VPN_USER_INVALID: "VPN device not valid.",
    E_NET_VPN_IP_MAX: "You have reached the maximum number of devices.",
    E_NET_DDNS_SVC_EXISTS: "Dynamic DDNS provider `%(provider)s` already exists",
    E_NET_DDNS_CONFIG: "Missing Dynamic DNS configuration. Check if username/domain and password/token are properly set for the chosen provider.",

    // Users
    E_USER_NOT_FOUND: "User %(user)s not found.",
    E_USER_PASSWD: "Unable to change the password for %(user)s.",
    E_USER_QUOTA: "Error occurred while setting the user quota: %(info)s.",
    E_USER_NAME: "Error occurred while changing username: %(info)s.",
    E_USER_SUDO: "Unable to change user's system privileges: %(info)s",
    E_NEW_USER: "Error occurred while creating a new user: %(info)s.",
    E_PERM_ADMIN: "Permission changes are disabled because this is the only administrator account.",
    E_DEL_ADMIN: "You cannot delete this account because this is the only administrator account.",
    E_USER_COPY_FILES: "Error occurred while moving files of the user %(user)s: %(info)s.",
    E_USER_DELETE: "Error occurred while deleting the user %(user)s: %(info)s.",
    E_USER_LOGIN_RESET: "Error occurred while resetting the login credentials for %(user)s: %(info)s.",
    E_USER_SYSTEM: "Error while retrieving the list of system users: %(info)s.",
    E_USER_UID: "Error while changing the uid for `%(username)s`: %(info)s.",
    E_USER_ALREADY_EXISTS: "User %(uname)s already exists.",

    // Filesystem
    E_FS_CH_PERM: "Unable to change permissions for %(path)s: %(info)s",
    E_FS_NOT_FILE: "The provided path `%(path)s` neither exists nor is a file.",
    E_FS_ZIP: "Error while zipping: `%(path)s`: %(info)s.",
    E_FS_UNZIP: "Error while unzipping: `%(path)s`: %(info)s.",
    E_FS_COPY: "Error while copying: `%(path)s`: %(info)s.",
    E_FS_MOVE: "Error while moving: `%(path)s`: %(info)s.",
    E_FS_MKDIR: "Error while creating the directory `%(path)s`: %(info)s.",

    // Events & Actions
    E_EVENT_INVALID: "Invalid event",
    E_ACTION_INVALID: "Invalid action",
    E_EVENT_INVALID_ACTION: "The action `%(action)s` cannot be used for the event `%(event)s`",
    E_EVENT_INVALID_PARAM: "Invalid parameter for the action `%(action)s`: %(parameter)s.",

    // System
    E_SYSTEM_UPDATES: "Error while retrieving system updates: %(info)s",
    E_SYSTEM_DIST: "Error while creating distribution archive: %(info)s.",
    E_APT_GET: "Unable to get system updates: %(info)s",
    E_APT_UNK: "Unable to update your current system. You may do so manually by accessing it via SSH."
};

export const ERROR_MESSAGES_IT: Record<string, string> = {
    // General
    E_UNKNOWN: "Errore Sconosciuto",
    E_UNKNOWN_RESPONSE: "Risposta sconosciuta dal server",
    E_PROPERTY: "Errore nell'ottenere il valore per la proprietà %(prop)s: %(info)s",
    E_CSRF: "Validazione form fallita.",
    E_UNKNOWN_METHOD: "Operazione sconosciuta.",
    E_READ_FILE: "Impossibile leggere il file %(file)s: %(info)s",
    E_REL_PATH: "Il percorso `%(path1)s` non è relativo a `%(path2)s`",
    E_SELINUX_PORT: "Errore durante l'acquisizione delle informazioni di sistema sulle porte: %(info)s",
    E_SYSTEMD_START: "Errore durante l'avvio del servizio di sistema %(services)s: %(info)s",
    E_SYSTEMD_STOP: "Errore durante l'arresto del servizio di sistema %(services)s: %(info)s",
    E_SYSTEMD_RESTART: "Errore durante il riavvio del servizio di sistema %(services)s: %(info)s",
    E_TOO_MANY_REQ: "Troppe richieste. Attendere un minuto.",
    E_INVALID_VALUE: "Valore non valido per %(prop)s: %(val)s",
    E_NO_PERM: "Non hai i permessi per eseguire questa operazione.",

    // Auth
    E_AUTH_ALREADY_CONFIG: "Hai già credenziali OTP configurate.",
    E_AUTH_INVALID: "Autorizzazione non valida.",
    E_AUTH_EXPIRED: "Autorizzazione scaduta.",
    E_AUTH_REVOKED: "Autorizzazione revocata.",
    E_AUTH_MALFORMED: "Autorizzazione malformata.",
    E_AUTH_NOT_CONF: "OTP non ancora configurato.",
    E_AUTH_WRONG_OTP: "OTP non valida.",

    // Storage Pool
    E_POOL_ALREADY_CONF: "L'archivio è già configurato.",
    E_POOL_NO_CONF: "Archivio non ancora configurato.",
    E_POOL_CONFIG: "L'archivio è configurato",
    E_POOL_DISK_UNAVAL: "Il disco %(dev)s non è disponibile per far parte di un nuovo archivio.",
    E_POOL_NEW: "Impossibile creare un nuovo archivio: %(info)s",
    E_POOL_DESTROY: "Impossibile cancellare l'archivio: %(info)s",
    E_POOL_REDUNDANCY_MIN: "Devi avere almeno 3 dischi per attivare la ridondanza.",
    E_POOL_EXPAND: "Errore durante l'aggiunta di %(dev)s: %(info)s",
    E_POOL_EXPAND_INFO: "Non è stato possibile ottenere le informazioni sul disco: %(dev)s",
    E_POOL_EXPAND_STATUS: "Non è stato possibile ottenere le informazioni sullo stato dell'espansione dell'archivio: %(info)s",
    E_POOL_KEY: "Errore durante il recupero della chiave di cifratura: %(info)s",
    E_POOL_KEY_IMPORT: "Errore nello restituire la chiave di cifratura: %(info)s",
    E_POOL_ATTACH: "Errore nell'importare la chiave di cifratura: %(info)s",
    E_POOL_LIST: "Impossibile ottenere la lista degli archivi esistenti.",
    E_POOL_RECOVERY: "Errore durante il recupero dell'archivio: %(info)s",
    E_POOL_DISKS: "Errore nell'ottenere la lista di dischi nell'archivio: %(info)s",
    E_POOL_DISK_REPLACE: "Impossible sostituire %(dev1)s con %(dev2)s: %(info)s",
    E_POOL_DETACH: "Errore nell'esportare l'archivio: %(info)s",
    E_POOL_MOUNT: "Errore nel montare l'archivio: %(info)s",
    E_POOL_UNMOUNT: "Errore nello smontare l'archivio: %(info)s",
    E_POOL_MOUNTED: "L'archivio è montato",
    E_POOL_UNMOUNTED: "L'archivio è smontato",
    E_POOL_SCRUB: "Errore nel verificare l'archivio: %(info)s.",
    E_POOL_INVALID_MOUNTPOINT: "Mountpoint non valido.",
    E_POOL_MOUNT_STATUS: "Errore durante il recupero delle informazioni per montare l'archivio: %(info)s",
    E_POOL_MOUNTPOINT: "Errore nel recuperare il mount point: %(info)s",
    E_POOL_RM_MOUNTPOINT: "Errore nel rimuovere il mount point: %(info)s",
    E_POOL_FORMAT: "Errore nel formattare l'archivio: %(info)s",
    E_POOL_CAPACITY: "Impossibile ottenere lo stato della capacità dell'archivio: %(info)s",
    E_POOL_OPENED: "Uno o più dischi non possono essere letti. Il tuo archivio NON PUÒ essere usato in questo stato.",
    E_POOL_DISK_MISSING: "Uno o più dischi sembrano assenti. Il tuo archivio NON PUÒ essere usato in questo stato.",
    E_POOL_CORRUPTED: "Le informazioni sul tuo archivio sono compromesse. Il recupero potrebbe essere possibile.",
    E_POOL_OUTDATED: "L'archivio sembra datato e non può più essere usato.",
    E_POOL_SNAPSHOT_NAME: "Lo snapshot `%(name)s` non è valido.",
    E_POOL_SNAPSHOT_CREATE: "Errore durante la creazione di un nuovo snapshot: %(info)s",
    E_POOL_SNAPSHOT_DELETE: "Errore durante la cancellazione dello snapshot `%(name)s`: %(info)s",
    E_POOL_SNAPSHOTS: "Errore nell'ottenere la lista degli snapshot: %(info)s",
    E_POOL_SNAPSHOT_ROLLBACK: "Errore nel tornare indietro a `%(name)s`: %(info)s",

    // Disks
    E_DISK_ATTACH: "Non è stato possibile aggiungere il nuovo disco all'archivio: %(details)s",
    E_DISK_FORMAT: "Errore durante la formattazione di %(dev)s: %(info)s",
    E_DISK_SELF_TEST: "Errore durante l'auto-test su %(dev)s: %(info)s",

    // Access Services
    E_ACCESS_ENABLED: "Errore durante l'attivazione del servizio %(service)s: %(info)s",
    E_ACCESS_DISABLED: "Errore durante la disattivazione del servizio %(service)s: %(info)s",
    E_ACCESS_DISABLING: "Non è stato possibile disattivare %(service)s. Disattivalo manualmente.",
    E_ACCESS_SERV_UNK: "Servizio d'accesso remoto %(service)s non riconosciuto.",
    E_ACCESS_PROP: "Errore durante la modifica della proprietà `%(prop)s`: %(info)s",

    // Network
    E_NET_CHANGE_STATE: "Errore nel cambiare lo stato dell'interfaccia di rete %(iface)s: %(info)s",
    E_NET_CONNECTION_STATUS: "Errore nell'ottenere lo stato connessione per %(iface)s: %(info)s",
    E_NET_INVALID_NETMASK: "Maschera di sottorete non valida",
    E_NET_INVALID_IP_ADDRESS: "Indirizzo IP non valido",
    E_NET_INVALID_GATEWAY: "Gateway non valido",
    E_NET_INVALID_DNS: "Indirizzo/i DNS non validi",
    E_NET_WIFI_LIST: "Errore nell'ottenere la lista delle reti WiFi per %(iface)s: %(info)s",
    E_NET_WIFI_CONNECT: "Impossibile connettersi a `%(ssid)s`: %(info)s",
    E_NET_WIFI_DEV: "Nessuna interfaccia WiFi valida rilevata.",
    E_NET_AP: "Impossibile creare hotspot su %(iface)s: %(info)s",
    E_NET_VPN_NOTCONF: "VPN non configurata.",
    E_NET_VPN_STATE: "Impossibile ottenere lo stato della VPN: %(info)s",
    E_NET_VPN_KEY: "Errore nell'ottenere la chiave VPN: %(info)s",
    E_NET_VPN_GEN_PRIVATE: "Errore durante la generazione della chiave privata: %(info)s",
    E_NET_VPN_GEN_PUBLIC: "Errore durante la generazione della chiave pubblica: %(info)s",
    E_NET_VPN_CONF: "Errore durante la lettura della configurazione VPN: %(info)s",
    E_NET_VPN_USER: "Dispositivo VPN `%(user)s` non trovato.",
    E_NET_VPN_USER_INVALID: "Dispositivo VPN non valido",
    E_NET_VPN_IP_MAX: "Hai raggiunto il numero massimo di dispositivi.",
    E_NET_DDNS_SVC_EXISTS: "Provider di DNS Dinamico `%(provider)s` già esistente",
    E_NET_DDNS_CONFIG: "Configurazione DNS Dinamico mancante. Controlla se username e password sono impostati correttamente.",

    // Users
    E_USER_NOT_FOUND: "Utente %(user)s non trovato.",
    E_USER_PASSWD: "Non è stato possibile cambiare la password per %(user)s.",
    E_USER_QUOTA: "Errore durante l'assegnazione della quota utente: %(info)s",
    E_USER_NAME: "Errore durante il cambio di nome utente: %(info)s",
    E_USER_SUDO: "Non è stato possibile cambiare i privilegi di sistema dell'utente: %(info)s",
    E_NEW_USER: "Errore durante la creazione di un nuovo utente: %(info)s",
    E_PERM_ADMIN: "I cambi di permessi sono disattivati poiché tu sei l'unico amministratore.",
    E_DEL_ADMIN: "Non puoi cancellare questo utente poiché sei l'unico amministratore.",
    E_USER_COPY_FILES: "Errore durante il trasferimento dei file dell'utente %(user)s: %(info)s",
    E_USER_DELETE: "Errore durante la cancellazione dell'utente %(user)s: %(info)s",
    E_USER_LOGIN_RESET: "Errore durante la reimpostazione delle credenziali di login per %(user)s: %(info)s.",
    E_USER_SYSTEM: "Errore nel recupero della lista degli utenti di sistema: %(info)s.",
    E_USER_UID: "Errore nel cambio uid per `%(username)s`: %(info)s.",
    E_USER_ALREADY_EXISTS: "L'utente %(uname)s esiste già.",

    // Filesystem
    E_FS_CH_PERM: "Non è stato possibile cambiare i permessi per %(path)s: %(info)s",
    E_FS_NOT_FILE: "Il percorso specificato `%(path)s` non esiste o non è un file.",
    E_FS_ZIP: "Errore durante la compressione di `%(path)s`: %(info)s.",
    E_FS_UNZIP: "Errore durante l'estrazione di `%(path)s`: %(info)s.",
    E_FS_COPY: "Errore durante la copia di `%(path)s`: %(info)s.",
    E_FS_MOVE: "Errore durante lo spostamento di `%(path)s`: %(info)s.",
    E_FS_MKDIR: "Errore durante la creazione della directory `%(path)s`: %(info)s.",

    // Events & Actions
    E_EVENT_INVALID: "Evento non valido",
    E_ACTION_INVALID: "Azione non valida",
    E_EVENT_INVALID_ACTION: "L'azione `%(action)s` non può essere usata per l'evento `%(event)s`",
    E_EVENT_INVALID_PARAM: "Parametro non valido per l'azione `%(action)s`: %(parameter)s.",

    // System
    E_SYSTEM_UPDATES: "Errore nel recupero degli aggiornamenti di sistema: %(info)s",
    E_SYSTEM_DIST: "Errore durante la creazione dell'archivio di distribuzione: %(info)s.",
    E_APT_GET: "Non è stato possibile ottenere gli aggiornamenti di sistema: %(info)s",
    E_APT_UNK: "Impossibile aggiornare il sistema. Puoi farlo manualmente via SSH."
};

/**
 * Format an error message string by substituting parameters.
 * Supports:
 * - Positional substitution from array: params[0], params[1]... matching %(key)s or %s in order
 * - Named substitution from object: params.key matching %(key)s
 */
export function formatErrorMessage(
    template: string,
    params?: (string | number)[] | Record<string, any> | null
): string {
    if (!params) {
        // Strip any unresolved %(...)s or %s tokens
        return template.replace(/%\([^)]+\)s/g, '').replace(/%s/g, '').trim();
    }

    if (Array.isArray(params)) {
        let idx = 0;
        let result = template.replace(/%\([^)]+\)s/g, (match) => {
            if (idx < params.length) {
                const val = params[idx++];
                return val !== null && val !== undefined ? String(val) : '';
            }
            return match;
        });

        idx = 0;
        result = result.replace(/%s/g, () => {
            if (idx < params.length) {
                const val = params[idx++];
                return val !== null && val !== undefined ? String(val) : '';
            }
            return '';
        });

        return result.replace(/%\([^)]+\)s/g, '').trim();
    }

    if (typeof params === 'object') {
        let result = template.replace(/%\(([^)]+)\)s/g, (match, key) => {
            if (key in params && params[key] !== null && params[key] !== undefined) {
                return String(params[key]);
            }
            return match;
        });
        return result.replace(/%\([^)]+\)s/g, '').trim();
    }

    return template;
}

/**
 * Get the localized error message for a given backend error code and parameters.
 */
export function getErrorMessage(
    code: string,
    params?: (string | number)[] | Record<string, any> | null,
    lang?: string
): string {
    const currentLang = (
        lang ||
        (typeof localStorage !== 'undefined'
            ? localStorage.getItem('appLanguage') || localStorage.getItem('i18nextLng')
            : null) ||
        (typeof navigator !== 'undefined' ? navigator.language : null) ||
        'en'
    ).toLowerCase();

    const isItalian = currentLang.startsWith('it');
    const dict = isItalian ? ERROR_MESSAGES_IT : ERROR_MESSAGES_EN;

    const template = dict[code] || ERROR_MESSAGES_EN[code];
    if (template) {
        return formatErrorMessage(template, params);
    }

    // Fallback message
    const fallbackTemplate = isItalian ? ERROR_MESSAGES_IT.E_UNKNOWN : ERROR_MESSAGES_EN.E_UNKNOWN;
    return `${fallbackTemplate} (${code})`;
}
