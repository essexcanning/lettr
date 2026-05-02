{ pkgs }: {
  deps = [
    pkgs.gcc-unwrapped
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.gcc
    pkgs.libffi
  ];
}
