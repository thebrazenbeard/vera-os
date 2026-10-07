{ config, lib, pkgs, ... }:

{
  networking.hostName = "veraos-vm";

  boot.kernelParams = [
    "console=tty0"
    "console=ttyS0,115200n8"
    "veraos.qualify=1"
  ];

  boot.loader.timeout = 1;

  systemd.services.veraos-vm-qualification = {
    description = "VeraOS headless VM qualification marker";
    wantedBy = [ "multi-user.target" ];
    after = [
      "veraos-composition-validate.service"
      "veraos-authority-boundary.service"
    ];
    requires = [
      "veraos-composition-validate.service"
      "veraos-authority-boundary.service"
    ];

    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = true;
      PrivateTmp = true;
    };

    script = ''
      set -eu

      manifest=/etc/vera-os/portfolio-composition.json
      total="$(${pkgs.jq}/bin/jq -r '.counts.total' "$manifest")"
      integrated="$(${pkgs.jq}/bin/jq -r '.counts.integrated' "$manifest")"
      excluded="$(${pkgs.jq}/bin/jq -r '.counts.excluded' "$manifest")"
      ambient="$(cat /run/veraos-ambient-protected-effect-authority)"

      marker="VERAOS_VM_BOOT_OK total=$total integrated=$integrated excluded=$excluded ambient_protected_effect_authority=$ambient"

      echo "$marker"
      if [ -w /dev/ttyS0 ]; then
        echo "$marker" > /dev/ttyS0
      fi

      mkdir -p /run/veraos
      printf '%s\n' "$marker" > /run/veraos/vm-qualification
    '';
  };
}
