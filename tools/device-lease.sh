#!/usr/bin/env bash
set -euo pipefail

# Advisory leases over the physical device fleet.
#
# APKs overwrite each other silently: one lane installing on a device another
# lane is capturing against destroys the second lane's evidence with no warning
# and no trace in the capture set. This makes the intent visible and expiring.
#
# ADVISORY, NOT ENFORCED. Nothing here can stop `adb install`. A lease reduces
# collisions; it does not prove which build produced a screenshot. Keep hashing
# the installed bundle before AND after a capture run regardless of the lease --
# prevention and verification are different jobs (docs/workflows/visual-capture.md).
#
# Leases EXPIRE. A crashed or killed holder must not deadlock the fleet, so a
# lease older than its TTL is stale and reclaimable without asking.
#
#   device-lease.sh claim   <serial> <holder> [--ttl MIN] [--hash H] [--note N]
#   device-lease.sh renew   <serial> <holder> [--ttl MIN] [--hash H]
#   device-lease.sh release <serial> <holder>
#   device-lease.sh steal   <serial> <holder> [--hash H]   # only if stale
#   device-lease.sh status  [serial]
#   device-lease.sh devices                                 # adb devices + lease state
#
# exit 0 acquired/ok | 3 held by someone else (fresh) | 4 not held / wrong holder

DIR="${POCKETPAL_LEASE_DIR:-$HOME/.local/state/pocketpal-dev-team/device-leases}"
DEFAULT_TTL="${POCKETPAL_LEASE_TTL_MIN:-45}"
mkdir -p "$DIR"

now() { date +%s; }
die() { echo "device-lease: $*" >&2; exit 2; }

_read() { # serial -> sets L_holder L_at L_ttl L_hash L_note
  local f="$DIR/$1"
  L_holder=""; L_at=0; L_ttl=$DEFAULT_TTL; L_hash=""; L_note=""
  [[ -f "$f" ]] || return 1
  # shellcheck disable=SC1090
  . "$f"
  return 0
}

_age_min() { echo $(( ( $(now) - ${1:-0} ) / 60 )); }
_stale()   { local age; age=$(_age_min "$L_at"); (( age >= L_ttl )); }

_write() { # serial holder ttl hash note
  local tmp; tmp="$(mktemp "$DIR/.tmp.XXXXXX")"
  { echo "L_holder='$2'"; echo "L_at=$(now)"; echo "L_ttl=$3"
    echo "L_hash='$4'";   echo "L_note='$5'"; } > "$tmp"
  mv -f "$tmp" "$DIR/$1"
}

_report() { # serial
  local age; age=$(_age_min "$L_at")
  local state="held"; _stale && state="STALE"
  printf '%-22s %-8s %-26s %3dm/%dm  %s %s\n' \
    "$1" "$state" "$L_holder" "$age" "$L_ttl" "${L_hash:0:16}" "$L_note"
}

cmd="${1:-status}"; shift || true

case "$cmd" in
  claim|renew|release|steal)
    serial="${1:-}"; holder="${2:-}"; shift 2 || true
    [[ -n "$serial" && -n "$holder" ]] || die "usage: $cmd <serial> <holder> [...]"
    ttl="$DEFAULT_TTL"; hash=""; note=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --ttl)  ttl="$2";  shift 2 ;;
        --hash) hash="$2"; shift 2 ;;
        --note) note="$2"; shift 2 ;;
        *) die "unknown flag: $1" ;;
      esac
    done
    ;;
esac

case "$cmd" in
  claim)
    if _read "$serial"; then
      if [[ "$L_holder" == "$holder" ]]; then
        _write "$serial" "$holder" "$ttl" "${hash:-$L_hash}" "${note:-$L_note}"
        echo "renewed (already yours)"; exit 0
      fi
      if _stale; then
        echo "device-lease: lease is STALE ($(_age_min "$L_at")m > ${L_ttl}m), held by $L_holder" >&2
        echo "  reclaim with: $0 steal $serial $holder" >&2
        exit 3
      fi
      echo "device-lease: HELD by $L_holder for $(_age_min "$L_at")m (ttl ${L_ttl}m)" >&2
      [[ -n "$L_note" ]] && echo "  note: $L_note" >&2
      echo "  ask them whether they still need it; do NOT install over a fresh lease." >&2
      exit 3
    fi
    _write "$serial" "$holder" "$ttl" "$hash" "$note"
    echo "claimed $serial for $holder (ttl ${ttl}m)"
    ;;
  renew)
    _read "$serial" || { echo "device-lease: no lease on $serial" >&2; exit 4; }
    [[ "$L_holder" == "$holder" ]] || { echo "device-lease: held by $L_holder, not $holder" >&2; exit 4; }
    _write "$serial" "$holder" "$ttl" "${hash:-$L_hash}" "${note:-$L_note}"
    echo "renewed $serial (ttl ${ttl}m)"
    ;;
  release)
    _read "$serial" || { echo "device-lease: no lease on $serial" >&2; exit 4; }
    [[ "$L_holder" == "$holder" ]] || { echo "device-lease: held by $L_holder, not $holder" >&2; exit 4; }
    rm -f "$DIR/$serial"; echo "released $serial"
    ;;
  steal)
    if _read "$serial"; then
      _stale || { echo "device-lease: lease on $serial is FRESH ($(_age_min "$L_at")m), held by $L_holder -- ask, do not steal" >&2; exit 3; }
      echo "device-lease: reclaiming STALE lease from $L_holder (${L_hash:0:16} was installed)" >&2
    fi
    _write "$serial" "$holder" "$DEFAULT_TTL" "$hash" "reclaimed-stale"
    echo "stole $serial for $holder"
    ;;
  status)
    s="${1:-}"
    if [[ -n "$s" ]]; then _read "$s" && _report "$s" || echo "$s: free"; exit 0; fi
    shopt -s nullglob; any=0
    for f in "$DIR"/*; do
      [[ "$(basename "$f")" == .tmp.* ]] && continue
      _read "$(basename "$f")" && { _report "$(basename "$f")"; any=1; }
    done
    (( any )) || echo "no leases held"
    ;;
  devices)
    adb devices 2>/dev/null | awk 'NR>1 && NF>=2 {print $1}' | while read -r s; do
      if _read "$s"; then _report "$s"; else printf '%-22s %-8s\n' "$s" "free"; fi
    done
    ;;
  *) die "unknown command: $cmd" ;;
esac
