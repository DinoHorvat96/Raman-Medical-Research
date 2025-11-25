#!/usr/bin/env python3
"""
USB Backup Drive Setup Helper (i.e. for Raspberry Pi)
Run this script to help configure your external USB drive for backups
"""

import os
import subprocess
import json


def run_command(cmd):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return str(e), 1


def find_usb_drives():
    """Find all USB drives connected to the system"""
    print("\n🔍 Searching for USB drives...")

    # Get list of block devices
    output, _ = run_command("lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,UUID,FSTYPE")

    if output:
        try:
            devices = json.loads(output)
            usb_drives = []

            for device in devices.get('blockdevices', []):
                if device['type'] == 'disk':
                    # Check if it's a USB device
                    usb_check, _ = run_command(
                        f"udevadm info -q property -n /dev/{device['name']} | grep ID_BUS | grep usb")
                    if usb_check:
                        print(f"\n✓ Found USB drive: /dev/{device['name']} ({device['size']})")
                        if 'children' in device:
                            for partition in device['children']:
                                print(f"  └─ Partition: /dev/{partition['name']}")
                                print(f"     Size: {partition['size']}")
                                print(f"     Filesystem: {partition.get('fstype', 'Unknown')}")
                                print(f"     UUID: {partition.get('uuid', 'Not available')}")
                                print(f"     Mounted at: {partition.get('mountpoint', 'Not mounted')}")

                                usb_drives.append({
                                    'device': f"/dev/{partition['name']}",
                                    'size': partition['size'],
                                    'fstype': partition.get('fstype'),
                                    'uuid': partition.get('uuid'),
                                    'mountpoint': partition.get('mountpoint')
                                })

            return usb_drives
        except json.JSONDecodeError:
            print("❌ Could not parse device information")

    return []


def setup_mount_point():
    """Create and configure the mount point"""
    mount_point = "/mnt/medical_backups"

    print(f"\n📁 Setting up mount point at {mount_point}")

    if not os.path.exists(mount_point):
        print(f"Creating {mount_point}...")
        os.makedirs(mount_point, exist_ok=True)
    else:
        print(f"✓ {mount_point} already exists")

    return mount_point


def generate_fstab_entry(drive_info, mount_point):
    """Generate the appropriate fstab entry for the drive"""
    uuid = drive_info['uuid']
    fstype = drive_info['fstype']

    if not uuid:
        print("⚠️  No UUID found. Using device path (less reliable)")
        identifier = drive_info['device']
    else:
        identifier = f"UUID={uuid}"

    # Generate appropriate mount options based on filesystem
    if fstype == 'ext4':
        options = "defaults,nofail,x-systemd.device-timeout=5"
        dump_pass = "0 2"
    elif fstype == 'ntfs':
        options = "defaults,nofail,uid=1000,gid=1000,dmask=022,fmask=022"
        dump_pass = "0 0"
    elif fstype == 'exfat':
        options = "defaults,nofail,uid=1000,gid=1000"
        dump_pass = "0 0"
    elif fstype == 'vfat':
        options = "defaults,nofail,uid=1000,gid=1000,umask=022"
        dump_pass = "0 0"
    else:
        options = "defaults,nofail"
        dump_pass = "0 0"

    fstab_entry = f"{identifier} {mount_point} {fstype} {options} {dump_pass}"

    return fstab_entry


def generate_docker_compose_snippet():
    """Generate docker-compose.yml configuration snippet"""

    snippet = """
services:
  web:
    build: .
    container_name: medical_web
    command: gunicorn --config gunicorn_config.py app:app
    environment:
      DB_NAME: ${DB_NAME:-raman_research_prod}
      DB_USER: ${DB_USER:-postgres}
      DB_PASSWORD: ${DB_PASSWORD}
      DB_HOST: ${DB_HOST:-postgres_container}
      DB_PORT: ${DB_PORT:-5432}
      SECRET_KEY: ${SECRET_KEY}
      FLASK_ENV: production
      BACKUP_DIR: ${BACKUP_DIR:-/mnt/medical_backups/raman_backups}
      BACKUP_RETENTION_DAYS: ${BACKUP_RETENTION_DAYS:-90}
    ports:
      - "5000:5000"
    networks:
      - medical_network
    volumes:
      - .:/app
      - ./backups:/backups
      - ./uploads:/app/uploads
      - /mnt/medical_backups:/mnt/medical_backups
    restart: unless-stopped
    healthcheck:
      test: [ "CMD", "curl", "-f", "http://localhost:5000/health" ]
      interval: 30s
      timeout: 3s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: medical_nginx
    ports:
      - "8088:80"
      # - "8443:443"  # Uncomment when SSL is configured
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      # - ./ssl:/etc/nginx/ssl:ro  # Uncomment when you add SSL certificates
    depends_on:
      - web
    networks:
      - medical_network
    restart: unless-stopped

networks:
  medical_network:
    driver: bridge

"""

    return snippet


def test_drive_write(mount_point):
    """Test if we can write to the drive"""
    print(f"\n🧪 Testing write access to {mount_point}...")

    test_file = os.path.join(mount_point, '.write_test')
    try:
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print("✓ Write test successful!")
        return True
    except Exception as e:
        print(f"❌ Write test failed: {e}")
        print("You may need to adjust permissions:")
        print(f"  sudo chown -R $(id -u):$(id -g) {mount_point}")
        return False


def check_drive_space(mount_point):
    """Check available space on the drive"""
    if os.path.exists(mount_point):
        statvfs = os.statvfs(mount_point)
        free_space = statvfs.f_frsize * statvfs.f_bavail
        total_space = statvfs.f_frsize * statvfs.f_blocks

        free_gb = free_space / (1024 ** 3)
        total_gb = total_space / (1024 ** 3)
        used_percent = ((total_space - free_space) / total_space) * 100

        print(f"\n💾 Drive Space Information:")
        print(f"  Total: {total_gb:.1f} GB")
        print(f"  Free: {free_gb:.1f} GB")
        print(f"  Used: {used_percent:.1f}%")

        if free_gb < 5:
            print("⚠️  Warning: Less than 5GB free space!")

        return free_gb


def main():
    print("=" * 60)
    print("🔧 RAMAN MEDICAL - USB BACKUP DRIVE SETUP HELPER")
    print("=" * 60)

    # Check if running as root (some operations need sudo)
    if os.geteuid() != 0:
        print("\n⚠️  Note: Some operations may require sudo privileges.")
        print("   Re-run with: sudo python3 setup_usb_backup.py")

    # Find USB drives
    drives = find_usb_drives()

    if not drives:
        print("\n❌ No USB drives found!")
        print("\nPlease:")
        print("1. Connect your USB drive")
        print("2. Wait a few seconds")
        print("3. Run this script again")
        return

    # If multiple drives, let user choose
    if len(drives) > 1:
        print("\n📋 Multiple USB drives found. Which one to use for backups?")
        for i, drive in enumerate(drives, 1):
            print(f"{i}. {drive['device']} ({drive['size']}, {drive['fstype']})")

        try:
            choice = int(input("\nEnter number (1-{}): ".format(len(drives))))
            selected_drive = drives[choice - 1]
        except (ValueError, IndexError):
            print("Invalid selection")
            return
    else:
        selected_drive = drives[0]

    print(f"\n✓ Selected drive: {selected_drive['device']}")

    # Setup mount point
    mount_point = setup_mount_point()

    # Mount the drive if not already mounted
    if not selected_drive['mountpoint']:
        print(f"\n🔗 Drive is not mounted. Attempting to mount...")
        cmd = f"sudo mount {selected_drive['device']} {mount_point}"
        print(f"Running: {cmd}")
        output, returncode = run_command(cmd)
        if returncode == 0:
            print("✓ Drive mounted successfully!")
        else:
            print(f"❌ Failed to mount: {output}")
            print("\nYou may need to:")
            print("1. Check if the filesystem is supported")
            print("2. Install necessary drivers (ntfs-3g for NTFS, exfat-utils for exFAT)")
            return
    else:
        print(f"✓ Drive already mounted at: {selected_drive['mountpoint']}")
        mount_point = selected_drive['mountpoint']

    # Test write access
    if test_drive_write(mount_point):
        # Check space
        check_drive_space(mount_point)

        # Generate fstab entry
        print("\n📝 Recommended /etc/fstab entry for auto-mounting:")
        print("-" * 50)
        fstab_entry = generate_fstab_entry(selected_drive, mount_point)
        print(fstab_entry)
        print("-" * 50)
        print("\nTo add this entry:")
        print("1. sudo nano /etc/fstab")
        print("2. Add the line above")
        print("3. Save and exit")
        print("4. Test with: sudo mount -a")

        # Generate docker-compose snippet
        print("\n🐳 Docker Configuration:")
        print("-" * 50)
        print(generate_docker_compose_snippet())

        # Create backup directory
        backup_dir = os.path.join(mount_point, "raman_backups")
        if not os.path.exists(backup_dir):
            try:
                os.makedirs(backup_dir, mode=0o755)
                print(f"\n✓ Created backup directory: {backup_dir}")
            except Exception as e:
                print(f"\n⚠️  Could not create backup directory: {e}")
                print(f"   Create manually: sudo mkdir -p {backup_dir}")
        else:
            print(f"\n✓ Backup directory exists: {backup_dir}")

        print("\n" + "=" * 60)
        print("✅ SETUP COMPLETE!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Update your /etc/fstab for auto-mounting")
        print("2. Update your docker-compose.yml")
        print("3. Restart your Docker containers")
        print("4. In the web interface, browse to:", mount_point)

    else:
        print("\n❌ Cannot proceed without write access to the drive")


if __name__ == "__main__":
    main()
