# Аудит PCOptimizer PRO v2.0.1 (2026-11-22)

Огляд коду після додавання HWiNFO Shared Memory та виправлення мапінгу температур.
Попередній аудит (`AUDIT_v1.6.1.md`) — історичний, стан v1.6.9.

## Перевірки

| Перевірка | Результат |
|---|---|
| `ruff check .` | All checks passed |
| `compileall app` | OK |
| `mypy app` (конфіг проєкту, platform win32) | було 10 помилок → **0** |
| Тести сенсорів/температур/i18n/settings/update/processes (Linux) | зелені, включно з новими |
| Повний `pytest` | потрібно перевірити на Windows частинами (див. PLAN) |

## Знахідки та статус

| ID | Пріоритет | Статус | Опис |
|---|---|---|---|
| B-01 | P1 | **fixed** | Регресія `temperature_kind`: сирий сенсор «System» (SuperIO) визначався як kind `system` і зникав з `board` у LHM. Додано `raw_temperature_kind` для бекендів; `temperature_kind` лишається для канонічних ключів. Тести `tests/test_lhm.py`. |
| B-02 | P1 | **fixed** | `psutil.TimeoutOccurred` не існує → `AttributeError` замість `False` у `ProcessService.terminate`, якщо процес не завершується за 3 с. Виправлено на `TimeoutExpired` + регресійний тест (падає на старому коді). |
| B-03 | P2 | **fixed** | Температура диска (S.M.A.R.T.) показувалась як «system». Новий kind `disk`; `zone_label` перекладає `hotspot`/`system`/`disk`. |
| B-04 | P2 | **fixed** | HWiNFO: нема перевірки застарілих даних; текст «Sensor Sharing» не збігався з назвою опції. Додано `hwinfo_poll_age` (поріг 120 с, невідомий штамп не ховає дані), текст «Shared Memory Support», підказка про 12-годинний ліміт free-версії (EN/UA). |
| B-05 | P2 | **fixed** | `.gitignore` не ігнорував `.venv-audit`; додано `.venv*/`. |
| B-06 | P2 | **fixed** | `pythonnet` був у `requirements.txt`, але не в `pyproject.toml`; `requires-python` обмежено `<3.15`. |
| B-07 | P3 | **fixed** | 10 помилок mypy (атрибути, присвоєння, lambda, `list` як тип, Sequence у dashboard). |
| B-08 | P3 | **fixed** | README: бейдж тестів без жорсткого числа, опис HWiNFO; PLAN: запис v2.0.2. |
| B-09 | P3 | open | Повний `pytest` одним запуском зависає (за PLAN) і дає native access violation при завершенні — потребує окремого розслідування. |
| B-10 | P3 | open | Перевірка `poll_time` HWiNFO написана за документацією структури; підтвердити на живому HWiNFO (див. нижче). |

## Перевірка на Windows перед релізом

1. `python -m ruff check .` і `python -m mypy app`.
2. `python -m pytest tests --ignore=tests/test_ui.py`, потім `tests/test_ui.py` окремо.
3. Запустити HWiNFO від адміністратора (Sensors + Shared Memory Support), відкрити «Температури»:
   CPU/Материнка/Відеокарта/hotspot/Диск заповнені, підписи українською.
4. Закрити вікно HWiNFO на 3 хв і переконатись, що температури не «застрягли»
   (якщо HWiNFO просто зникає, джерело переходить на LHM/ACPI з підказкою).
5. Тільки після цього: bump до 2.0.2, збірка exe/installer, release.
