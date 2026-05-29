"""
set_grade.py — Live presentation grader for Sigma Intelligence Platform dashboard.

Usage:
  Grade one student:
    python set_grade.py "Suroj Verma" master
    python set_grade.py "Pawan Singh" complete
    python set_grade.py "Harshit" missing

  Grade an entire team at once:
    python set_grade.py --team team1 master
    python set_grade.py --team team3 complete

  Show current grades:
    python set_grade.py --status

  Valid grades:
    master   → 👑 Gold Crown  (found the trap, strong defense, live demo worked)
    complete → ✅ Green Tick  (solid presentation, partial trap analysis)
    partial  → ~  Partial     (presented but shallow / missed the trap)
    missing  → ✗  Red X       (did not present / no live demo)

After running, the script:
  1. Updates repo/api/manual_overrides.json
  2. Git adds + commits + pushes to GitHub
  3. Vercel picks up the push and redeploys in ~60 seconds
  4. Hit Refresh on the dashboard to see the updated icons

Day number defaults to 9. Override with --day N.
"""

import sys
import os
import json
import subprocess

REPO_ROOT      = os.path.dirname(os.path.abspath(__file__))
OVERRIDES_PATH = os.path.join(REPO_ROOT, 'api', 'manual_overrides.json')

VALID_GRADES   = {'master', 'complete', 'partial', 'missing'}
GRADE_ICONS    = {
    'master':   '👑 Gold Crown',
    'complete': '✅ Green Tick',
    'partial':  '~  Partial',
    'missing':  '✗  Red X',
}


def load():
    with open(OVERRIDES_PATH, encoding='utf-8') as f:
        return json.load(f)


def save(data):
    with open(OVERRIDES_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def git_push(message):
    cmds = [
        ['git', '-C', REPO_ROOT, 'add', 'api/manual_overrides.json'],
        ['git', '-C', REPO_ROOT, 'commit', '-m', message],
        ['git', '-C', REPO_ROOT, 'push'],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 and 'nothing to commit' not in result.stdout:
            print(f'[git] {" ".join(cmd[2:])}')
            if result.stderr:
                print(f'      {result.stderr.strip()}')


def show_status(data, day):
    day_key = str(day)
    grades = data.get(day_key, data.get(day, {}))
    if not grades:
        print(f'No grades set for Day {day} yet.')
        return
    print(f'\nDay {day} Presentation Grades:')
    print(f'{"Name":<25} {"Grade":<12} {"Icon"}')
    print('-' * 50)
    for name, grade in sorted(grades.items()):
        print(f'{name:<25} {grade:<12} {GRADE_ICONS.get(grade, grade)}')
    masters  = sum(1 for g in grades.values() if g == 'master')
    complete = sum(1 for g in grades.values() if g == 'complete')
    missing  = sum(1 for g in grades.values() if g == 'missing')
    print(f'\nSummary: 👑 {masters} masters  ✅ {complete} complete  ✗ {missing} not graded')


def grade_student(data, day, name, grade):
    # Find matching key (case-insensitive)
    day_key = str(day)
    if day_key not in data:
        data[day_key] = {}

    # Case-insensitive match against existing keys
    matched_key = None
    for existing in data[day_key]:
        if existing.lower() == name.lower():
            matched_key = existing
            break

    if matched_key is None:
        # New name — add it
        matched_key = name
        data[day_key][matched_key] = 'missing'

    old_grade = data[day_key][matched_key]
    data[day_key][matched_key] = grade
    return matched_key, old_grade


def grade_team(data, day, team_name, grade):
    teams = data.get('_teams', {})
    if team_name not in teams:
        available = ', '.join(teams.keys())
        print(f'[ERROR] Unknown team "{team_name}". Available: {available}')
        sys.exit(1)
    members = teams[team_name]
    results = []
    for member in members:
        key, old = grade_student(data, day, member, grade)
        results.append((key, old, grade))
    return results


def main():
    args = sys.argv[1:]

    # Parse --day N
    day = 9
    if '--day' in args:
        idx = args.index('--day')
        day = int(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    data = load()

    # --status: show current grades and exit
    if '--status' in args or not args:
        show_status(data, day)
        return

    # --team <name> <grade>
    if '--team' in args:
        idx = args.index('--team')
        if idx + 2 > len(args):
            print('[ERROR] Usage: python set_grade.py --team team1 master')
            sys.exit(1)
        team_name = args[idx + 1]
        grade     = args[idx + 2].lower()
        if grade not in VALID_GRADES:
            print(f'[ERROR] Invalid grade "{grade}". Use: {", ".join(VALID_GRADES)}')
            sys.exit(1)
        results = grade_team(data, day, team_name, grade)
        save(data)
        print(f'\nGraded {team_name} → {GRADE_ICONS[grade]}')
        for name, old, new in results:
            print(f'  {name}: {old} → {new}')
        msg = f'Grade Day{day}: {team_name} = {grade}'
        git_push(msg)
        print(f'\n[OK] Pushed. Vercel redeploys in ~60s → refresh the dashboard.')
        return

    # Single student: python set_grade.py "Name" grade
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    name  = args[0]
    grade = args[1].lower()

    if grade not in VALID_GRADES:
        print(f'[ERROR] Invalid grade "{grade}". Valid options: {", ".join(VALID_GRADES)}')
        sys.exit(1)

    matched_key, old_grade = grade_student(data, day, name, grade)
    save(data)

    print(f'\n[OK] Day {day} grade set:')
    print(f'     {matched_key}: {old_grade} → {grade}  {GRADE_ICONS[grade]}')

    msg = f'Grade Day{day}: {matched_key} = {grade}'
    git_push(msg)
    print(f'\n[OK] Pushed. Vercel redeploys in ~60 seconds → refresh the dashboard.')


if __name__ == '__main__':
    main()
