#!/usr/bin/env python3
"""Create a project copy by editing only year-related OOXML fields (stdlib).

The repo ships the template spec as assets/templates/确认表模板.md, not a binary
master. Build the master from that spec (or ask for one), then pass it via --template.
"""
import argparse
import io
from pathlib import Path
import re
import sys
import zipfile

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[1] / 'assets/templates/确认表模板.xlsx'
# Keep all other XML byte-for-byte to preserve drawings, relationships, freezes and styles.
VALIDATION = re.compile(rb'(<dataValidation\b[^>]*\bsqref="K2:K1000"[^>]*>.*?<formula1>)(.*?)(</formula1>)', re.S)


def parameterize(template: bytes, years):
    if years is not None:
        if len(years) != 3 or len(set(years)) != 3 or years != sorted(years):
            raise ValueError('规划期须为三个不同、递增的年度')
        if any(isinstance(y, bool) or not isinstance(y, int) or not 1900 <= y <= 9999 for y in years):
            raise ValueError('年度须为 1900 至 9999 的整数')
    items = ['已完成', '待确认'] + (['{}年'.format(y) for y in years] if years else [])
    explanation = ('近期：{}年；中期：{}年；远期：{}年。实际年度由客户逐项确认，未明确填待确认。'.format(*years)
                   if years else '近期、中期、远期对应年度待项目确认；排序不自动等于完成年度。未明确时留空或选择“待确认”。')
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(template)) as src, zipfile.ZipFile(output, 'w') as dst:
        matches = 0
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == 'xl/worksheets/sheet3.xml':
                formula = ('"' + ','.join(items) + '"').encode('utf-8')
                data, matches = VALIDATION.subn(lambda m: m.group(1) + formula + m.group(3), data)
            elif info.filename == 'xl/worksheets/sheet1.xml':
                pattern = rb'(<c\b[^>]*\br="C17"[^>]*>).*?(</c>)'
                data, count = re.subn(pattern, lambda m: m.group(1) + b'<is><t>' + explanation.encode('utf-8') + b'</t></is>' + m.group(2), data, flags=re.S)
                if count != 1:
                    raise ValueError('找不到唯一年度说明 C17，拒绝生成')
            dst.writestr(info, data)
    if matches != 1:
        raise ValueError('找不到唯一年度下拉 K2:K1000，拒绝生成')
    return output.getvalue()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--template', type=Path, default=DEFAULT_TEMPLATE)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--years', type=int, nargs=3)
    a = p.parse_args(argv)
    try:
        if not a.template.is_file():
            raise OSError('找不到母版：%s；请按 assets/templates/确认表模板.md 自制后用 --template 指定' % a.template)
        result = parameterize(a.template.read_bytes(), a.years)
        # Exclusive create; never replace a current client workbook.
        with a.output.open('xb') as handle:
            handle.write(result)
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        print(str(e), file=sys.stderr)
        return 1
    print('已生成项目副本；请复核客户口径、年度、图片与下拉。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
