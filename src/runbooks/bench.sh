#!/bin/bash
set -euo pipefail

# ==============================================================================
# Script Name: Simulation Workload (bench.sh)
# Description: Simula vari tipi di carico (CPU, Memoria, I/O) per test di monitoraggio
# Usage:       ./bench.sh <TYPE> <DURATION_SEC> [INTENSITY]
# ==============================================================================

# --- 1. Arguments & Help ---
usage() {
    echo "Usage: $0 <TYPE> <DURATION_SEC> [INTENSITY]"
    echo ""
    echo "Arguments:"
    echo "  TYPE          Tipo di workload: cpu, mem, io, all"
    echo "  DURATION_SEC  Durata della simulazione in secondi"
    echo "  INTENSITY     Intensità (default: 1). Numero di processi paralleli o fattore di scala."
    echo ""
    echo "Esempio:"
    echo "  $0 cpu 30 4    # Stressa la CPU per 30 secondi con 4 processi"
    exit 1
}

if [ "$#" -lt 2 ]; then
    usage
fi

TYPE=$1
DURATION=$2
INTENSITY=${3:-1}

# --- 2. Helper Functions ---
log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1"; }
log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2; }

stress_cpu() {
    log_info "Avvio stress CPU (intensità: $INTENSITY) per $DURATION secondi..."
    for i in $(seq 1 "$INTENSITY"); do
        (
            end=$((SECONDS + DURATION))
            while [ $SECONDS -lt $end ]; do
                # Operazione ad alto carico CPU nativa Unix
                # Generiamo dati casuali e ne calcoliamo l'hash
                if command -v md5sum &> /dev/null; then
                    head -c 10M /dev/urandom | md5sum > /dev/null 2>&1 || true
                else
                    head -c 10M /dev/urandom | md5 > /dev/null 2>&1 || true
                fi
            done
        ) &
    done
}

stress_mem() {
    log_info "Avvio stress Memoria (circa $((INTENSITY * 50))MB) per $DURATION secondi..."
    # Simuliamo l'uso di memoria creando stringhe larghe (approccio bash-only)
    (
        local data=""
        # Creiamo una stringa di circa 50MB * INTENSITY
        # Usiamo /dev/urandom e base64 per occupare spazio velocemente
        for i in $(seq 1 "$INTENSITY"); do
            data+="$(head -c 50000000 /dev/urandom | base64)"
        done
        log_info "Memoria allocata ($(( ${#data} / 1024 / 1024 )) MB). In attesa di $DURATION secondi..."
        sleep "$DURATION"
        log_info "Rilascio memoria."
        unset data
    ) &
}

stress_io() {
    log_info "Avvio stress I/O (scrittura file temporanei) per $DURATION secondi..."
    for i in $(seq 1 "$INTENSITY"); do
        (
            end=$((SECONDS + DURATION))
            while [ $SECONDS -lt $end ]; do
                dd if=/dev/zero of="/tmp/workload_test_${i}_${SECONDS}" bs=1M count=50 conv=fdatasync status=none 2>/dev/null
                rm "/tmp/workload_test_${i}_${SECONDS}"
            done
        ) &
    done
}

# --- 4. Main Logic ---
main() {
    log_info "Inizio simulazione workload: $TYPE"

    # Verifica dipendenze minime
    if [ "$TYPE" == "cpu" ] || [ "$TYPE" == "all" ]; then
        if ! command -v md5sum &> /dev/null && ! command -v md5 &> /dev/null; then
            log_error "Il comando 'md5sum' o 'md5' è richiesto per lo stress CPU."
            exit 1
        fi
    fi

    case "$TYPE" in
        cpu)
            stress_cpu
            ;;
        mem)
            stress_mem
            ;;
        io)
            stress_io
            ;;
        all)
            stress_cpu
            stress_mem
            stress_io
            ;;
        *)
            log_error "Tipo di workload non valido: $TYPE"
            usage
            ;;
    esac

    # Attendiamo la fine dei processi in background
    log_info "Monitoraggio in corso..."
    wait
    log_info "Simulazione completata con successo."
}

main "$@"
