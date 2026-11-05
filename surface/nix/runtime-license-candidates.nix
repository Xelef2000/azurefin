# Preliminary metadata, NOT a closure match or a redistribution clearance.
# Supply the source pinned by nix-installer's flake.lock. Review upstream source
# notices and match actual store outputs before treating these as final records.
{ nixpkgsSource }:
let
  pkgs = import nixpkgsSource { system = "aarch64-linux"; };
  names = [
    "acl" "aws-c-auth" "aws-c-cal" "aws-c-common" "aws-c-compression"
    "aws-c-event-stream" "aws-c-http" "aws-c-io" "aws-c-mqtt" "aws-c-s3"
    "aws-c-sdkutils" "aws-checksums" "aws-crt-cpp" "boehmgc" "boost189"
    "brotli" "busybox" "bzip2" "cacert" "curl" "editline" "glibc" "hwloc"
    "keyutils" "krb5" "libarchive" "libblake3" "libgit2" "libidn2" "libpsl"
    "libseccomp" "libsodium" "libssh2" "libunistring" "libxml2" "llhttp"
    "lowdown" "mimalloc" "nghttp2" "nghttp3" "ngtcp2" "onetbb" "openssl"
    "pcre2" "publicsuffix-list" "s2n-tls" "sqlite" "xz" "zlib" "zstd"
  ];
  describe = name:
    let p = pkgs.${name}; in {
      attribute = name;
      pname = p.pname or p.name;
      version = p.version or null;
      licenses = map (l: {
        spdxId = l.spdxId or null;
        fullName = l.fullName or null;
        url = l.url or null;
        free = l.free or null;
      }) (pkgs.lib.toList (p.meta.license or []));
      recipe = p.meta.position or null;
      homepage = p.meta.homepage or null;
    };
in map describe names
