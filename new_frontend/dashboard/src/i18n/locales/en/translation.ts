import { sharedEn } from '@nms/shared';

export const en = {
  ...sharedEn,
  app: {
    ...sharedEn.app,
    title: "NAS Management System",
    subtitle: "Storage & Network Dashboard",
    welcome_back: "Welcome back",
    notifications: "Notifications",
    no_notifications: "No new notifications",
    quick_status: "System Overview"
  },
  nav: {
    dashboard: "Dashboard",
    disks: "Disk Management",
    network: "Network",
    users: "Users",
    access: "Remote Access",
    advanced: "Advanced"
  },
  dashboard: {
    title: "Dashboard",
    welcome: "Welcome",
    system_status: "System is healthy and operational",
    refresh: "Refresh",
    refreshing: "Refreshing...",
    loading_data: "Loading system data...",
    error_loading: "Error loading dashboard metrics"
  },
  widgets: {
    storage: {
      title: "Storage Array",
      used: "Used",
      free: "Free",
      total: "Total",
      quota: "Your Quota",
      quota_unlimited: "Unlimited",
      status: "Array Status",
      mounted: "Mounted",
      unmounted: "Unmounted",
      configured: "Configured",
      not_configured: "Not Configured",
      health: "Healthy"
    },
    disks: {
      title: "Disks Overview",
      disks_in_pool: "Disks in Array",
      sys_disks: "System Disks",
      state: "Status",
      size: "Size",
      model: "Model",
      temp: "Temperature",
      no_disks: "No disks detected"
    },
    network: {
      title: "Network Interfaces",
      interface: "Interface",
      ip: "IP Address",
      status: "Status",
      up: "Active",
      down: "Down",
      vpn: "VPN (WireGuard)",
      connected: "Connected",
      disconnected: "Disconnected",
      no_interfaces: "No network interfaces found"
    },
    access: {
      title: "Remote Services",
      active_count: "Active Services",
      running: "Running",
      stopped: "Stopped",
      enable: "Enable",
      disable: "Disable",
      no_services: "No access services configured"
    },
    system: {
      title: "System Information",
      hostname: "Hostname",
      os: "Operating System",
      kernel: "Kernel",
      uptime: "Uptime",
      cpu: "CPU Load",
      memory: "Memory Usage",
      updates: "Updates Available",
      up_to_date: "System is up to date"
    },
    sensors: {
      title: "Hardware Sensors",
      temperature: "Temperatures",
      fans: "Cooling Fans",
      normal: "Normal",
      rpm: "RPM",
      no_sensors: "No sensor readings available"
    }
  },
  actions: {
    reboot: "Reboot",
    shutdown: "Shutdown",
    logout: "Logout",
    cancel: "Cancel",
    confirm: "Confirm",
    reboot_confirm: "Are you sure you want to reboot the system?",
    shutdown_confirm: "Are you sure you want to power off the system?",
    logout_confirm: "Are you sure you want to log out?",
    rebooting: "Initiating system reboot...",
    shutting_down: "Initiating system shutdown..."
  }
};
