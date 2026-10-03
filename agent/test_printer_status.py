import unittest
from unittest.mock import patch
import subprocess

from printer_status import parse_ipp_status, query_printer


class PrinterStatusTests(unittest.TestCase):
    def test_detects_no_paper(self):
        status = parse_ipp_status(
            'printer-state (enum) = stopped\n'
            'printer-state-reasons (keyword) = media-empty\n'
            'printer-state-message (textWithoutLanguage) = Printer is stopped. No Paper.\n'
        )
        self.assertEqual(status.error, 'Printer error: printer is out of paper')

    def test_detects_paper_jam(self):
        status = parse_ipp_status(
            'printer-state (enum) = stopped\n'
            'printer-state-reasons (keyword) = media-jam\n'
            'printer-state-message (textWithoutLanguage) = Paper jam\n'
        )
        self.assertEqual(status.error, 'Printer error: paper jam')

    def test_detects_empty_ink(self):
        status = parse_ipp_status(
            'printer-state (enum) = idle\n'
            'printer-state-reasons (keyword) = marker-supply-empty\n'
        )
        self.assertEqual(status.error, 'Printer error: ink supply is empty')

    def test_detects_unreachable_reason(self):
        status = parse_ipp_status(
            'printer-state (enum) = idle\n'
            'printer-state-reasons (keyword) = offline-error\n'
        )
        self.assertEqual(status.error, 'Printer error: printer is offline')

    def test_reports_low_ink_as_warning_without_blocking_print(self):
        status = parse_ipp_status(
            'printer-state (enum) = idle\n'
            'printer-state-reasons (keyword) = marker-supply-low\n'
            'marker-levels (1setOf integer) = 5,80\n'
            'marker-low-levels (1setOf integer) = 10,10\n'
            'marker-names (1setOf nameWithoutLanguage) = BK,C\n'
        )
        self.assertFalse(status.error)
        self.assertIn('ink supply is low', status.warnings[0])
        self.assertIn('bk ink is low (5%, threshold 10%)', status.warnings)

    def test_unknown_supply_values_are_not_interpreted_as_levels(self):
        status = parse_ipp_status(
            'printer-state (enum) = idle\n'
            'printer-state-reasons (keyword) = none\n'
            'marker-levels (1setOf integer) = -3\n'
            'marker-low-levels (1setOf integer) = -3\n'
        )
        self.assertFalse(status.error)
        self.assertEqual(status.warnings, ())

    def test_fails_if_state_is_missing(self):
        with self.assertRaisesRegex(RuntimeError, 'did not include printer-state'):
            parse_ipp_status('printer-state-reasons (keyword) = none\n')

    def test_reports_printer_unreachable(self):
        result = subprocess.CompletedProcess(
            args=['ipptool'],
            returncode=1,
            stdout='',
            stderr='Unable to connect to printer',
        )
        with patch('printer_status.get_printer_uri', return_value='ipp://192.0.2.1/ipp/print'):
            with patch('printer_status.subprocess.run', return_value=result):
                with self.assertRaisesRegex(RuntimeError, 'Printer unreachable or IPP query failed'):
                    query_printer('brother')

    def test_reports_stopped_without_specific_reason(self):
        status = parse_ipp_status(
            'printer-state (enum) = stopped\n'
            'printer-state-reasons (keyword) = none\n'
            'printer-state-message (textWithoutLanguage) = Printer is stopped\n'
        )
        self.assertEqual(status.error, 'Printer error: Printer is stopped')


if __name__ == '__main__':
    unittest.main()
