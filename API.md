# API


## /v1/auth/otp/get/{prop}

### GET

Auth Get Property

## /v1/auth/otp

### PATCH

Set a new OTP for the admin user (or with the use with a valid token)

### POST

Verify OTP

## /v1/auth/otp/refresh

### POST

Refresh access token

## /v1/auth/logout

### POST

Log out from NMS

## /v1/auth/token/first_login

### GET

Generates a login token to allow the user to set a new OTP

## /v1/net/io

### GET

Returns the network statistics of Input/Output

## /v1/net/ifaces

### GET

Returns the network interfaces

## /v1/net/{iface}/list

### GET

Returns the list of wifi networks

## /v1/net/{iface}/connect

### POST

Connect to a wifi network

## /v1/net/vpn/pubkey

### GET

Provides the VPN public key

## /v1/net/vpn/public-ip

### GET

Provides the VPN public ip

## /v1/net/vpn/peers

### GET

Returns the list of VPN peers

### DELETE

Deletes a VPN peer

### POST

Adds a VPN peer

## /v1/net/vpn/gen-keys

### POST

Generates private and public key for the VPN service

## /v1/net/vpn

### GET

Returns the VPN configuration

### PATCH

Changes VPN configuration

## /v1/net/vpn/{action}

### POST

Enable or disable the VPN service

## /v1/net/{iface}/{action}

### POST

Enable or disable a network interface

## /v1/net/{iface}/{ip_version}

### PATCH

Changes the configuration of a network interface

## /v1/net/ddns

### GET

Returns the list of Dynamic DNS providers

## /v1/net/ddns/{provider}/start

### POST

Starts the given Dynamic DNS provider

## /v1/net/ddns/{provider}/stop

### POST

Starts the given Dynamic DNS provider

## /v1/pool/get/disks

### GET

Get the list of disks in the array

## /v1/pool/get/attachable-disks

### GET

Get the list of new disks that can be attached/added to the array

## /v1/pool/get/{prop}

### GET

Get a configuration/status pool property

## /v1/pool/mount

### POST

Mount the disk array

## /v1/pool/unmount

### POST

Unmount the disk array

## /v1/pool/format

### POST

Destroy and recreate a new disk array

## /v1/pool/detach

### POST

Detach the disk array (it will not be visible anymore) without deleting it

## /v1/pool/attach

### POST

Attach an existing disk array

## /v1/pool/create

### POST

Create a new disk array

## /v1/pool/destroy

### POST

Destroy the new disk array

## /v1/pool/import/key

### POST

Import encryption key for a disk array

## /v1/pool/recover

### POST

Attempts to recover from errors in the disk array

## /v1/pool/replace

### POST

Replace a device with another device in the disk array

## /v1/pool/scrub

### POST

Start disk array scrubbing operation

## /v1/pool/expand

### POST

Add a new disk to the pool

## /v1/pool/snapshot

### GET

Get the list of snapshots

## /v1/pool/snapshot/{snapshot_name}

### POST

Create a new snapshot

### DELETE

Delete the given snapshot snapshot

### PATCH

Delete the given snapshot snapshot

## /v1/disks/get/sys-disks

### GET

Provides all the disks installed in the system

## /v1/disks/get/disks

### GET

Provides all the disks in the array, attachable, and detached

## /v1/disks/format

### POST

Format a specific disk

## /v1/system/get/{prop}

### GET

Get a configuration/status system property

## /v1/system/shutdown

### POST

Power off the NAS

## /v1/system/restart

### POST

Reboot the NAS

## /v1/system/restart-systemd-services

### POST

Restart main system services

## /v1/system/apt/{action}

### POST

Perform apt-get update/upgrade commands

## /v1/system/nms/updates

### GET

Provides information related to the newest NMS version retrieved.

### POST

Retrieve information for new NMS updates from GitHub

### PATCH

Update NMS

## /v1/system/task/{task_id}

### GET

Get the information of a background task

## /v1/system/logs/{filter}

### GET

Retrieve system logs

## /v1/system/test

### GET

Test checking if the client/server connection works properly

## /v1/system/make-dist

### POST

Create a tarball archive with NMS distribution. The output file will be saved in NMS root directory

## /v1/services/get

### GET

Get the list of access services

## /v1/services/enable/{service_id}

### POST

Enable an access service

## /v1/services/update/{service_id}

### POST

Update the settings in an access service

## /v1/services/disable/{service_id}

### POST

Disable an access service

## /v1/fs/mountpoint

### DELETE

Delete the directory of the mount point

## /v1/fs/browse/{path}

### GET

Get the list of files of the logged user.

## /v1/fs/browse

### GET

Get the list of files of the logged user.

## /v1/fs/checksum/{path}

### GET

Get MD5 checksum of the specified file

## /v1/fs/mkdir

### POST

Create a new directory within the user space.

## /v1/fs/mv

### POST

Rename or move a file/directory within the user space.

## /v1/fs/cp

### POST

Copy a file/directory within the user space.

## /v1/fs/upload

### POST

Initiate an upload session via TUS protocol

### OPTIONS

Options Upload

## /v1/fs/upload/{upload_id}

### HEAD

Retrieve information regarding an upload session

### PATCH

Upload a chunk of a file upload session

### DELETE

Terminate Upload

## /v1/fs/item/{filename}

### GET

Download File

### DELETE

Delete a file/directory within the user space.

## /v1/fs/preview/{filename}

### HEAD

Generate a token for preview (this is to accommodate <video>)

### GET

Generate a stream for previews. The token required here must be obtained by the HEAD method to the same endpoint.

## /v1/fs/zip

### POST

Compress the provided files in a compressed zip archive.

## /v1/fs/unzip/{filename}

### POST

Decompress most of compressed archives (despite the name)

## /v1/fs/quota

### GET

Quota usage of the logged user.

## /v1/users/get

### GET

Get information of the logged user

## /v1/users/get/sys

### GET

Get the list of system usernames that have not been associated to other user

## /v1/users/get/all

### GET

Get the list of all users

## /v1/users/set/fullname

### POST

Set Fullname

## /v1/users/set/quota

### POST

Set Quota

## /v1/users/set/username

### POST

Set Username

## /v1/users/set/sys-user

### POST

Assign a specific system user (Unix) to the given user (their username will be renamed)

## /v1/users/set/sudo

### POST

Add or remove a user from sudoers

## /v1/users/set/permissions

### POST

Set user from permissions

## /v1/users/service/{service}

### POST

Change the password for a specific access service

## /v1/users/new

### POST

Create a new user

## /v1/users/delete

### POST

Delete a user

## /v1/users/reset/{username}

### POST

Delete a user