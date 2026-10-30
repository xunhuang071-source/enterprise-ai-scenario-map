#!/usr/bin/env python3
"""Generate research questions, not research findings. Python 3.8+, stdlib only."""
import argparse
from datetime import date
import json
import sys
from typing import Dict, List, Optional


def nonempty(value: str) -> str:
    value = value.strip()
    if not value:
        raise argparse.ArgumentTypeError('不能为空')
    return value


def valid_year(value: str) -> int:
    try:
        year = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('年度必须是整数')
    if not 1900 <= year <= 9999:
        raise argparse.ArgumentTypeError('年度须为 1900 至 9999')
    return year


class CompanyResearcher:
    """Backward-compatible company_name/country API; all facts remain unknown."""
    def __init__(self, company_name: str, country: str = '中国',
                 industry: Optional[str] = None, research_year: Optional[int] = None,
                 time_window: Optional[str] = None):
        self.company_name = nonempty(company_name)
        self.country = nonempty(country)
        self.industry = nonempty(industry) if industry is not None else None
        if research_year is not None and time_window is not None:
            raise ValueError('research_year 与 time_window 不能同时设置')
        if research_year is not None:
            valid_year(str(research_year))
        self.time_window = (nonempty(time_window) if time_window is not None else
                            str(research_year) if research_year is not None else
                            '{} {}'.format(date.today().year - 1, date.today().year))

    def research_company(self) -> Dict:
        print('[框架] {}：待按问题补充证据，并非已完成调研'.format(self.company_name), file=sys.stderr)
        return self._generate_company_framework()

    def _generate_company_framework(self) -> Dict:
        return {
            'company_name': self.company_name,
            'country': self.country,
            'research_status': '问题框架已生成；企业事实、行业判断和应用效果待验证',
            'company_overview': {'introduction': '待调研', 'established_year': None, 'team_size': None},
            'business_info': {'main_business': '待调研', 'business_model': '待调研', 'core_services': []},
            'products': {'core_products': [], 'product_features': '待调研'},
            'tags': {'industry_tags': [self.industry] if self.industry else [],
                     'industry_status': '用户指定待核验' if self.industry else '待识别',
                     'business_tags': [], 'market_position': '待调研'},
            'customers': {'main_customers': [], 'customer_segments': '待调研'},
            'time_window': self.time_window,
            'research_queries': self._generate_research_queries(),
            'industry_research_queries': self._generate_industry_queries(),
            'evidence_fields': ['判断', '事实或假设', '来源定位', '发布日期', '查阅日期', '待核验事项'],
            'simulation_note': '允许模拟访谈发现问题，输出需标为模拟，不等于客户确认'
        }

    def _generate_research_queries(self) -> List[str]:
        return ['{} {}'.format(self.company_name, item) for item in [
            '公司介绍 成立时间 发展历程', '主营业务 价值链 部门职责',
            '核心产品 服务范围', '行业分类 竞争环境', '客户群体 使用者',
            '团队规模 组织架构（如有公开信息）', '现有系统 数据 AI应用',
            '业务目标 财务状况（如有公开信息）']]

    def _generate_industry_queries(self) -> List[Dict[str, str]]:
        if not self.industry:
            return [{'purpose': '识别行业和核心业务后再生成针对性查询',
                     'query': '{} 主营业务 所属行业'.format(self.company_name),
                     'collect': '核实实际行业；可以先结合内部材料分析，无强制搜索顺序'}]
        return [
            {'purpose': '行业现状与趋势', 'query': '{} 痛点 业务趋势 {}'.format(self.industry, self.time_window),
             'collect': '行业问题与趋势；不得自动写成本企业事实'},
            {'purpose': 'AI实践机制', 'query': '{} AI应用 实施 案例 {}'.format(self.industry, self.time_window),
             'collect': '单位、范围、投运状态、来源及可借鉴条件；不设案例配额'},
            {'purpose': '可验证的业务变化', 'query': '{} AI 业务流程 岗位 实践 {}'.format(self.industry, self.time_window),
             'collect': '任务、输入输出、人机交接、KPI与测试线索；不直接迁移效果数字'}]

    def format_output(self, company_info: Dict, format_type: str = 'markdown') -> str:
        if format_type == 'json':
            return json.dumps(company_info, ensure_ascii=False, indent=2, allow_nan=False)
        if format_type != 'markdown':
            raise ValueError('不支持的输出格式')
        return self._format_markdown(company_info)

    def _format_markdown(self, company_info: Dict) -> str:
        lines = ['# {} 企业调研问题框架'.format(self.company_name), '',
                 '**状态**：{}'.format(company_info['research_status']),
                 '**国家／地区参数**：{}（待核验，不是注册地址结论）'.format(self.country),
                 '**时间窗**：{}'.format(self.time_window),
                 '**行业**：{}'.format(self.industry or '待识别'), '', '## 企业问题']
        lines += ['{}. {}'.format(i, q) for i, q in enumerate(company_info['research_queries'], 1)]
        lines += ['', '## 行业问题']
        for item in company_info['industry_research_queries']:
            lines += ['', '### {}'.format(item['purpose']), item['query'], item['collect']]
        lines += ['', '## 验证与模拟', company_info['simulation_note'],
                  '已有材料可先分析；按缺口补搜索。事实、目标和假设分别记录。']
        return '\n'.join(lines) + '\n'


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--company-name', required=True, type=nonempty)
    parser.add_argument('--country', default='中国', type=nonempty)
    parser.add_argument('--format', choices=['markdown', 'json'], default='markdown')
    parser.add_argument('--industry', type=nonempty)
    window = parser.add_mutually_exclusive_group()
    window.add_argument('--research-year', type=valid_year)
    window.add_argument('--time-window', type=nonempty)
    args = parser.parse_args(argv)
    researcher = CompanyResearcher(args.company_name, args.country, args.industry,
                                   args.research_year, args.time_window)
    print(researcher.format_output(researcher.research_company(), args.format))
    return 0


if __name__ == '__main__':
    sys.exit(main())
