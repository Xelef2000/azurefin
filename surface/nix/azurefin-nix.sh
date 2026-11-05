# shellcheck shell=sh
# System-wide POSIX shell integration. No user dotfiles are modified.
# Append rather than prepend: existing system/Homebrew choices keep precedence.
for _azurefin_nix_bin in \
    "${HOME}/.nix-profile/bin" \
    "${XDG_STATE_HOME:-${HOME}/.local/state}/nix/profile/bin" \
    /nix/var/nix/profiles/default/bin
do
    [ -d "$_azurefin_nix_bin" ] || continue
    case ":${PATH-}:" in
        *:"$_azurefin_nix_bin":*) ;;
        *) PATH="${PATH:+${PATH}:}$_azurefin_nix_bin" ;;
    esac
done
export PATH
unset _azurefin_nix_bin
