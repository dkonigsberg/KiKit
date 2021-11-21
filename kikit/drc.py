from pcbnewTransition import pcbnew, isV6
import sys
import tempfile
import re
from dataclasses import dataclass, field
from kikit.drc_ui import ReportLevel

@dataclass
class Violation:
    type: str
    description: str
    rule: str
    severity: str
    objects: list = field(default_factory=list)

    def __str__(self):
        head = f"[{self.type}]: {self.description} Severity: {self.severity}\n  {self.rule}"
        tail = "\n".join(["  " + x for x in self.objects])
        return "\n".join([head] + [tail])

def readViolations(reportFile):
    violations = []
    line = reportFile.readline()
    while True:
        headerMatch = re.match(r'\[(.*)\]: (.*)\n', line)
        if headerMatch is None:
            break
        line = reportFile.readline()
        bodyMatch = re.match(r'\s*(.*); Severity: (.*)', line)
        if bodyMatch is None:
            break
        v = Violation(
            type = headerMatch.group(1),
            description = headerMatch.group(2),
            rule = bodyMatch.group(1),
            severity = bodyMatch.group(2))
        line = reportFile.readline()
        while line.startswith("    "):
            v.objects.append(line.strip())
            line = reportFile.readline()
        violations.append(v)

    return line, violations

def readReport(reportFile):
    report = {}
    line = reportFile.readline()
    while True:
        if len(line) == 0:
            break
        if re.match(r'\*\* Found \d+ DRC violations \*\*', line):
            line, v = readViolations(reportFile)
            report["drc"] = v
            continue
        if re.match(r'\*\* Found \d+ unconnected pads \*\*', line):
            line, v = readViolations(reportFile)
            report["unconnected"] = v
            continue
        if re.match(r'\*\* Found \d+ Footprint errors \*\*', line):
            line, v = readViolations(reportFile)
            report["footprint"] = v
        line = reportFile.readline()
    return report

def runImpl(boardfile, useMm, strict, level):
    try:
        if not isV6():
            raise RuntimeError("This feature is available only with KiCAD 6.")
        units = pcbnew.EDA_UNITS_MILLIMETRES if useMm else EDA_UNITS_INCHES
        b = pcbnew.LoadBoard(boardfile)
        with tempfile.NamedTemporaryFile(mode="w+") as tmpFile:
            result = pcbnew.WriteDRCReport(b, tmpFile.name, units, strict)
            assert result

            tmpFile.seek(0)
            report = readReport(tmpFile)

            failed = False
            errorName = {
                "drc": "DRC violations",
                "unconnected": "unconnected pads",
                "footprint": "footprints errors"
            }
            for k, v in report.items():
                if len(v) == 0:
                    continue
                failed = False
                failedCases = []
                for x in v:
                    thisFailed = False
                    if level == ReportLevel.warning and x.severity == "warning":
                        thisFailed = True
                    if x.severity == "error":
                        thisFailed = True
                    if thisFailed:
                        failedCases.append(x)
                    failed = failed or thisFailed
                if failedCases:
                    print(f"** Found {len(failedCases)} {errorName[k]}: **")
                    for x in failedCases:
                        print(x)
                print("\n")
            if not failed:
                print("No DRC errors found.")
            else:
                print("Found some DRC violations. See the report above.")
            sys.exit(failed)
    except Exception as e:
        sys.stderr.write("An error occurred: " + str(e) + "\n")
        sys.exit(1)
