"""标准库 CLI 对照执行器；模型输出需语义评审，脚本不自动判教学成功。"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def parse_events(raw):
    events = []
    for line in raw.decode('utf-8', errors='replace').splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    texts = [e['item']['text'] for e in events
             if e.get('item', {}).get('type') == 'agent_message']
    completed = any(e.get('type') == 'turn.completed' for e in events)
    failed = any(e.get('type') in ('error', 'turn.failed') for e in events)
    sid = next((e['thread_id'] for e in events if e.get('type') == 'thread.started'), None)
    commands = [e['item'].get('command', '') for e in events
                if e.get('item', {}).get('type') == 'command_execution']
    return {'text': '\n\n'.join(texts), 'completed': completed and not failed,
            'sid': sid, 'commands': commands}


def model_turn(args, condition, case, suffix, prompt, sid=None):
    label = condition + '_' + case['id'] + suffix
    result_path = args.output / (label + '.json')
    if result_path.exists():
        return json.loads(result_path.read_text(encoding='utf-8'))
    workspace = args.output / 'workspaces' / condition
    workspace.mkdir(parents=True, exist_ok=True)
    config = json.loads(args.disable_config.read_text(encoding='utf-8'))['config']
    cmd = ['codex', '--no-daemon', '-c', config,
           '-c', 'features.multi_agent=false', '-c', 'features.multi_agent_v2=false', 'exec']
    if sid:
        cmd += ['resume', sid]
    else:
        cmd += ['-C', str(workspace), '-s', 'read-only']
    cmd += ['--skip-git-repo-check', '--json', '-']
    env = os.environ.copy()
    proxy = urllib.request.getproxies().get('https')
    if proxy:
        env.update(HTTPS_PROXY=proxy, HTTP_PROXY=urllib.request.getproxies().get('http', proxy))
    status = 'failed'
    try:
        proc = subprocess.run(cmd, input=prompt.encode('utf-8'), capture_output=True,
                              env=env, timeout=args.timeout)
        raw, diagnostic = proc.stdout, proc.stderr
        parsed = parse_events(raw)
        if proc.returncode == 0 and parsed['completed'] and parsed['text']:
            status = 'completed'
    except subprocess.TimeoutExpired as exc:
        raw, diagnostic = exc.stdout or b'', exc.stderr or b''
        parsed = parse_events(raw)
        status = 'timeout'
    (args.output / (label + '.jsonl')).write_bytes(raw)
    (args.output / (label + '.log')).write_bytes(diagnostic)
    result = dict(condition=condition, case=case['id'], turn=suffix or 'initial',
                  status=status, prompt=prompt, **parsed)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(label + ': ' + status, flush=True)
    return result


def run_case(args, condition, case):
    # 相同学习案例正文；仅显式Skill处理不同，不发送预期错因、策略或评分标准。
    if condition == 'ordinary':
        prefix = '请作为普通Codex进行这段教学对话，不使用任何Skill。不要联网，不操作项目文件。\n'
    else:
        prefix = ('使用项目中的 $ai-study-mentor-skill 继续这段教学对话。'
                  '先读取 .agents/skills/ai-study-mentor-skill/SKILL.md 和其中需要的参考文件。'
                  '不要读取 tests 中的文件，不要联网，不修改文件。\n')
    first = model_turn(args, condition, case, '', prefix + case['prompt'])
    if case.get('followup') and first['status'] == 'completed' and first['sid']:
        model_turn(args, condition, case, '_followup', case['followup'], first['sid'])
    return first


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--disable-config', type=Path, required=True,
                        help='由实际 skills/list 生成并验证全禁用的进程覆盖JSON，不含凭据')
    parser.add_argument('--conditions', nargs='+', choices=['ordinary', 'v013', 'v02'], required=True)
    parser.add_argument('--split', choices=['dev', 'heldout', 'all'], default='all')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT):
        parser.error('原始结果必须放在仓库外，避免发布日志或会话信息')
    if not 1 <= args.workers <= 2:
        parser.error('workers须为1或2，避免大量并发模型请求')
    args.output.mkdir(parents=True, exist_ok=True)
    cases = json.loads((ROOT / 'tests/V0.2案例.json').read_text(encoding='utf-8'))
    assert len({c['id'] for c in cases}) == len(cases)
    tasks = [(condition, c) for c in cases for condition in args.conditions
             if args.split == 'all' or c['split'] == args.split]
    if any(condition != 'ordinary' and not (args.output / 'workspaces' / condition /
           '.agents/skills/ai-study-mentor-skill/SKILL.md').is_file() for condition, _ in tasks):
        parser.error('请先在条件工作区安装对应冻结版本；不得用可变源码替换旧版')
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_case, args, condition, case) for condition, case in tasks]
        for future in as_completed(futures):
            future.result()
    summary = [{'file': p.name, 'status': json.loads(p.read_text(encoding='utf-8'))['status']}
               for p in sorted(args.output.glob('*.json'))
               if p.name.startswith(('ordinary_', 'v013_', 'v02_'))]
    (args.output / '执行汇总.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('全部结果均保留；completed仅指模型请求完成，不等于教学通过。', flush=True)


if __name__ == '__main__':
    main()
