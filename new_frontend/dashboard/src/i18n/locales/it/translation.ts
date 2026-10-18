import { sharedIt } from '@nms/shared';

export const it = {
  ...sharedIt,
  app: {
    ...sharedIt.app,
    title: "NAS Management System",
    subtitle: "Pannello Storage & Rete",
    welcome_back: "Bentornato",
    notifications: "Notifiche",
    no_notifications: "Nessuna nuova notifica",
    quick_status: "Panoramica Sistema"
  },
  nav: {
    dashboard: "Dashboard",
    disks: "Gestione Dischi",
    network: "Rete",
    users: "Utenti",
    access: "Accesso Remoto",
    advanced: "Avanzate"
  },
  dashboard: {
    title: "Dashboard",
    welcome: "Benvenuto",
    system_status: "Il sistema è operativo e in salute",
    refresh: "Aggiorna",
    refreshing: "Aggiornamento in corso...",
    loading_data: "Caricamento metriche di sistema...",
    error_loading: "Errore durante il caricamento dei dati"
  },
  widgets: {
    storage: {
      title: "Storage Array",
      used: "Usato",
      free: "Libero",
      total: "Totale",
      quota: "La tua Quota",
      quota_unlimited: "Illimitata",
      status: "Stato Array",
      mounted: "Montato",
      unmounted: "Smontato",
      configured: "Configurato",
      not_configured: "Non Configurato",
      health: "In Salute"
    },
    disks: {
      title: "Panoramica Dischi",
      disks_in_pool: "Dischi nell'Array",
      sys_disks: "Dischi di Sistema",
      state: "Stato",
      size: "Dimensione",
      model: "Modello",
      temp: "Temperatura",
      no_disks: "Nessun disco rilevato"
    },
    network: {
      title: "Interfacce di Rete",
      interface: "Interfaccia",
      ip: "Indirizzo IP",
      status: "Stato",
      up: "Attivo",
      down: "Non Attivo",
      vpn: "VPN (WireGuard)",
      connected: "Connesso",
      disconnected: "Disconnesso",
      no_interfaces: "Nessuna interfaccia di rete trovata"
    },
    access: {
      title: "Servizi di Accesso",
      active_count: "Servizi Attivi",
      running: "In Esecuzione",
      stopped: "Fermato",
      enable: "Attiva",
      disable: "Disattiva",
      no_services: "Nessun servizio di accesso configurato"
    },
    system: {
      title: "Informazioni di Sistema",
      hostname: "Nome Host",
      os: "Sistema Operativo",
      kernel: "Kernel",
      uptime: "Tempo di Attività",
      cpu: "Carico CPU",
      memory: "Uso Memoria",
      updates: "Aggiornamenti Disponibili",
      up_to_date: "Il sistema è aggiornato"
    },
    sensors: {
      title: "Sensori Hardware",
      temperature: "Temperature",
      fans: "Ventole",
      normal: "Normale",
      rpm: "RPM",
      no_sensors: "Nessuna lettura sensori disponibile"
    }
  },
  actions: {
    reboot: "Riavvia",
    shutdown: "Spegni",
    logout: "Esci",
    cancel: "Annulla",
    confirm: "Conferma",
    reboot_confirm: "Sei sicuro di voler riavviare il sistema?",
    shutdown_confirm: "Sei sicuro di voler spegnere il sistema?",
    logout_confirm: "Sei sicuro di voler uscire dalla sessione?",
    rebooting: "Riavvio del sistema in corso...",
    shutting_down: "Spegnimento del sistema in corso..."
  }
};
