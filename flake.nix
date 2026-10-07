{
  description = "VeraOS — governed Vera operating substrate";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      lib = nixpkgs.lib;
      veraosVm = lib.nixosSystem {
        inherit system;
        modules = [
          "${nixpkgs}/nixos/modules/installer/cd-dvd/installation-cd-minimal.nix"
          ./nixos/modules/veraos-base.nix
          ./nixos/hosts/vm-qualification.nix
        ];
      };
    in {
      nixosConfigurations.veraos-vm = veraosVm;
      packages.${system}.veraos-vm-iso =
        veraosVm.config.system.build.isoImage;
      checks.${system}.veraos-vm =
        veraosVm.config.system.build.toplevel;
    };
}
