{ config, lib, pkgs, ... }:

let
  compositionManifest =
    ../../architecture/portfolio/VERA_OS_PORTFOLIO_COMPOSITION_V1.json;
  compositionSource = ../../src;
in
{
  networking.hostName = lib.mkDefault "veraos";

  environment.etc."vera-os/portfolio-composition.json".source =
    compositionManifest;

  environment.systemPackages = with pkgs; [
    bash
    coreutils
    curl
    git
    jq
    python3
  ];

  systemd.services.veraos-composition-validate = {
    description = "Validate VeraOS exact portfolio composition";
    wantedBy = [ "multi-user.target" ];
    before = [ "multi-user.target" ];
    requiredBy = [ "multi-user.target" ];

    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = true;
      PrivateTmp = true;
    };

    script = ''
      export PYTHONPATH=${compositionSource}
      ${pkgs.python3}/bin/python - <<'PY'
import json
from pathlib import Path

from veraos.composition import validate_manifest

path = Path("/etc/vera-os/portfolio-composition.json")
manifest = json.loads(path.read_text(encoding="utf-8"))
validate_manifest(manifest)

counts = manifest["counts"]
assert counts["total"] == 84
assert counts["integrated"] + counts["excluded"] == counts["total"]
assert manifest["authority"]["ambient_protected_effect_authority"] is False
print(
    "VERAOS_COMPOSITION_OK "
    f"total={counts['total']} "
    f"integrated={counts['integrated']} "
    f"excluded={counts['excluded']}"
)
PY
    '';
  };

  systemd.targets.veraos-runtime = {
    description = "VeraOS governed runtime target";
    requires = [ "veraos-composition-validate.service" ];
    after = [ "veraos-composition-validate.service" ];
  };

  systemd.services.veraos-authority-boundary = {
    description = "Record VeraOS protected-effect authority boundary";
    wantedBy = [ "veraos-runtime.target" ];
    after = [ "veraos-composition-validate.service" ];

    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = true;
      PrivateTmp = true;
    };

    script = ''
      echo "PATRICK_EXPLICIT_EXACT_TARGET_EFFECT" > /run/veraos-authority-source
      echo "false" > /run/veraos-ambient-protected-effect-authority
    '';
  };

  system.stateVersion = "24.11";
}
