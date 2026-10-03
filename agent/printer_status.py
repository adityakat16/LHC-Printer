import re
import subprocess
from dataclasses import dataclass


IPP_TEST_FILE = '/usr/share/cups/ipptool/get-printer-attributes.test'

FATAL_REASONS = {
    'cover-open',
    'door-open',
    'developer-empty',
    'fuser-over-temp',
    'fuser-under-temp',
    'input-tray-missing',
    'input-tray-failure',
    'input-tray-jam',
    'interlock-open',
    'media-empty',
    'media-jam',
    'media-needed',
    'media-path-failure',
    'media-tray-failure',
    'marker-failure',
    'output-area-full',
    'output-tray-failure',
    'output-tray-jam',
    'output-tray-missing',
    'opd-life-over',
    'shutdown',
    'timed-out',
    'toner-empty',
    'marker-supply-empty',
    'offline',
    'spool-area-full',
    'interpreter-error',
    'interpreter-memory-overflow',
}

REASON_LABELS = {
    'cover-open': 'cover is open',
    'door-open': 'door is open',
    'developer-empty': 'developer supply is empty',
    'fuser-over-temp': 'printer fuser is too hot',
    'fuser-under-temp': 'printer fuser is too cold',
    'input-tray-missing': 'paper tray is missing',
    'input-tray-failure': 'paper input tray failure',
    'input-tray-jam': 'paper jam in input tray',
    'interlock-open': 'printer safety interlock is open',
    'media-empty': 'printer is out of paper',
    'media-jam': 'paper jam',
    'media-needed': 'printer needs paper',
    'media-path-failure': 'paper feed path failure',
    'media-tray-failure': 'paper tray failure',
    'marker-failure': 'ink/toner supply failure',
    'output-area-full': 'output tray is full',
    'output-tray-failure': 'output tray failure',
    'output-tray-jam': 'paper jam in output tray',
    'output-tray-missing': 'output tray is missing',
    'opd-life-over': 'optical drum life has ended',
    'shutdown': 'printer is shut down',
    'timed-out': 'printer connection timed out',
    'toner-empty': 'toner/ink is empty',
    'marker-supply-empty': 'ink supply is empty',
    'marker-supply-low': 'ink supply is low',
    'offline': 'printer is offline',
    'spool-area-full': 'printer spool storage is full',
    'interpreter-error': 'printer could not interpret the document',
    'interpreter-memory-overflow': 'printer ran out of memory processing the document',
}

WARNING_REASONS = {
    'marker-supply-low',
    'toner-low',
    'media-low',
    'output-area-almost-full',
    'marker-waste-almost-full',
    'opd-near-eol',
    'developer-low',
}


@dataclass(frozen=True)
class PrinterStatus:
    state: str
    reasons: tuple
    message: str
    warnings: tuple

    @property
    def error(self):
        fatal = [reason for reason in self.reasons if _base_reason(reason) in FATAL_REASONS]
        if self.state == 'stopped' or fatal:
            details = [_reason_label(reason) for reason in fatal]
            if not details:
                details = [self.message] if self.message else ['printer is stopped']
            return 'Printer error: ' + '; '.join(dict.fromkeys(details))
        return ''


def _attribute(output, name):
    match = re.search(
        rf'^\s*{re.escape(name)}\s+\([^)]*\)\s*=\s*(.*?)\s*$',
        output,
        re.MULTILINE | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ''


def _base_reason(reason):
    return reason.lower().removesuffix('-error').removesuffix('-warning').removesuffix('-report')


def _reason_label(reason):
    normalized = _base_reason(reason)
    return REASON_LABELS.get(normalized, normalized.replace('-', ' '))


def _values(raw):
    return tuple(
        item.strip().lower()
        for item in raw.split(',')
        if item.strip() and item.strip().lower() != 'none'
    )


def parse_ipp_status(output):
    state = _attribute(output, 'printer-state').lower()
    if not state:
        raise RuntimeError('IPP response did not include printer-state')

    reasons = _values(_attribute(output, 'printer-state-reasons'))
    message = _attribute(output, 'printer-state-message')
    warnings = [
        _reason_label(reason)
        for reason in reasons
        if _base_reason(reason) in WARNING_REASONS
    ]

    levels = _values(_attribute(output, 'marker-levels'))
    low_levels = _values(_attribute(output, 'marker-low-levels'))
    names = _values(_attribute(output, 'marker-names'))
    for index, level in enumerate(levels):
        if index >= len(low_levels):
            break
        try:
            current = int(level)
            low = int(low_levels[index])
        except ValueError:
            continue
        if current >= 0 and low >= 0 and current <= low:
            supply = names[index] if index < len(names) else f'supply {index + 1}'
            warning = f'{supply} ink is low ({current}%, threshold {low}%)'
            if warning not in warnings:
                warnings.append(warning)

    return PrinterStatus(state, reasons, message, tuple(warnings))


def get_printer_uri(printer_name, cups_server='', timeout=10):
    command = ['lpstat']
    if cups_server:
        command.extend(['-h', cups_server])
    command.extend(['-v', printer_name])
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f'Unable to contact CUPS: {exc}') from exc
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Unable to read the CUPS printer URI')
    match = re.search(r'device for [^:]+:\s*(\S+)', result.stdout)
    if not match:
        raise RuntimeError(f'CUPS returned no device URI for printer {printer_name}')
    return match.group(1)


def query_printer(printer_name, cups_server='', timeout=10):
    printer_uri = get_printer_uri(printer_name, cups_server, timeout)
    command = ['ipptool', '-tv', printer_uri, IPP_TEST_FILE]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise RuntimeError('ipptool is missing; install cups-ipp-utils to query printer status') from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'Printer at {printer_uri} did not respond to IPP status query') from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f'IPP status query failed for {printer_uri}'
        raise RuntimeError(f'Printer unreachable or IPP query failed: {detail}')

    status = parse_ipp_status(result.stdout)
    if status.error:
        raise RuntimeError(status.error)
    return status
