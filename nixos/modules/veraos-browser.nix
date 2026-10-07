{ config, lib, pkgs, ... }:

let
  browserPolicy = {
    schema = "VERA_OS_BROWSER_POLICY_V1";
    interactive = true;
    automation = true;
    defaultProfilePersistence = "EPHEMERAL";
    ambientCredentialAccess = false;
    protectedEffectAuthority = false;
    credentialMutationAuthority = false;
    protectedActionsRequireEffectBroker = true;
    governedDownloadRoot = "/var/lib/vera-browser/downloads";
  };
in
{
  users.groups.vera-browser = {};

  users.users.vera-browser = {
    isSystemUser = true;
    group = "vera-browser";
    home = "/var/lib/vera-browser";
    createHome = true;
    description = "VeraOS governed browser automation identity";
  };

  environment.systemPackages = with pkgs; [
    chromium
    firefox
  ];

  environment.etc."vera-os/browser-policy.json".text =
    builtins.toJSON browserPolicy;

  systemd.tmpfiles.rules = [
    "d /var/lib/vera-browser 0750 vera-browser vera-browser -"
    "d /var/lib/vera-browser/downloads 0750 vera-browser vera-browser -"
    "d /var/lib/vera-browser/profiles 0750 vera-browser vera-browser -"
  ];

  # Browser engines are installed as capabilities, not started as ambient
  # privileged services. Interactive UI or automation must receive an
  # explicit VeraOS browser capability grant.
}
