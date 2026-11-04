{
  description = "Development environment for the conlang generator";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python312;
          spacy = python.pkgs.spacy;
          model = python.pkgs.buildPythonPackage {
            pname = "en-core-web-sm";
            version = "3.8.0";
            format = "wheel";
            src = pkgs.fetchurl {
              url = "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl";
              hash = "sha256-GTJCnbcn1L/z3u1rNM/AXfF3lPSlLusmz4ko98Gg+4U=";
            };
            propagatedBuildInputs = [ spacy ];
            doCheck = false;
          };
          pythonEnv = python.withPackages (packages: [
            packages.pytest
            packages.spacy
            model
          ]);
        in
        assert nixpkgs.lib.versionAtLeast spacy.version "3.8";
        assert nixpkgs.lib.versionOlder spacy.version "3.9";
        {
          default = pkgs.mkShell {
            packages = [ pythonEnv pkgs.git ];
          };
        });
    };
}