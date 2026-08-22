<div align="center">

# 🪑 ErgoBoost

**Помощник по эргономике рабочего места в реальном времени: следит за осанкой, усталостью глаз и расстоянием до экрана через веб-камеру — и становится точнее по мере использования.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6%20(Qt)-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![MediaPipe](https://img.shields.io/badge/CV-MediaPipe%20%2B%20OpenCV-orange)](https://developers.google.com/mediapipe)
[![scikit-learn](https://img.shields.io/badge/ML-scikit--learn-F7931E?logo=scikitlearn&logoColor=white)](https://scikit-learn.org/)
[![PySpark](https://img.shields.io/badge/Big%20Data-PySpark-E25A1C?logo=apachespark&logoColor=white)](https://spark.apache.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**[🇬🇧 Read in English](README.md) | [🇷🇺 Русский](README.ru.md)**

![ErgoBoost ловит сутулость и предупреждает пользователя](docs/screenshots/shift.gif)

</div>

## Что это такое?

**ErgoBoost** — десктопное приложение под Windows, которое живёт в трее и в реальном времени анализирует картинку с веб-камеры, чтобы поймать вредные для здоровья привычки до того, как они превратятся в боль: сутулость, слишком близкое сидение к экрану, редкое моргание. Это не просто набор жёстко заданных правил — приложение обучает собственный классификатор на *ваших* данных осанки в фоновом потоке и подменяет модель "на лету", не прерывая работу камеры.

Проект сделан как дипломная работа по специальности "Информатика", но это полноценное, устанавливаемое приложение — не ноутбук и не proof-of-concept. Полная методология описана в [`docs/diploma_paper.pdf`](docs/diploma_paper.pdf).

## 📸 Демонстрация

| Калибровка | Детекция сутулости (forward-shift) | Детекция бокового наклона |
|:---:|:---:|:---:|
| ![Калибровка](docs/screenshots/colib.gif) | ![Детекция сутулости](docs/screenshots/shift.gif) | ![Детекция наклона](docs/screenshots/tilt.gif) |
| Разовая настройка эталона — посидите прямо пару секунд, чтобы ErgoBoost запомнил вашу нейтральную позу | Голова/плечи уходят вперёд → статус переключается в BAD → отсчёт → предупреждение на экране | Линия плеч наклоняется в сторону — ловится тем же механизмом, независимо от сутулости |

## ✨ Возможности

- **Отслеживание позы в реальном времени** — сдвиг головы вперёд и наклон плеч, вычисляются по ключевым точкам MediaPipe `PoseLandmarker` и сглаживаются скользящим средним, чтобы убрать дрожание.
- **Детекция усталости глаз** — определение морганий через Eye Aspect Ratio (EAR) на базе `FaceLandmarker`, со скользящей частотой морганий в минуту.
- **Контроль дистанции до экрана** — статусы "слишком близко" / "слишком далеко" на основе относительной ширины лица и персональной калибровки.
- **Разовая персональная калибровка** — короткий шаг калибровки фиксирует вашу нейтральную позу как эталон, поэтому отклонения считаются относительно вас, а не усреднённого человека.
- **ML-классификатор осанки с online learning** — `GradientBoostingClassifier` / `RandomForestClassifier` определяет статус OK/BAD и периодически дообучается на свежих данных сессии в фоновом потоке. Новая модель заменяет текущую только если превосходит порог по F1 — подмена происходит "на лету", без простоя.
- **Валидация без утечки данных** — кросс-валидация через `GroupKFold`, сгруппированную по `session_id`, так что модель никогда не проверяется на кадрах из той же сессии, на которой обучалась.
- **Затемнение экрана** — если плохая поза сохраняется дольше короткого времени ожидания, экран затемняется на всех мониторах, пока вы не выпрямитесь (или не нажмёте Escape).
- **Напоминания о перерывах** — мягкий/жёсткий лимит непрерывной работы, с детекцией отсутствия, чтобы ставить таймер на паузу, когда вы реально отошли.
- **Локальная аутентификация и история сессий** — аккаунты с хешированием PBKDF2-SHA256, лог сессий в SQLite, графики трендов и PDF-отчёты в один клик.
- **Пайплайн для больших данных** — параллельный PySpark-пайплайн (`ml/train_pyspark.py`, `analytics/pyspark_analytics.py`) для обучения и аналитики на масштабе, с которым pandas на одной машине уже не справится.

## 🛠 Технологический стек

| Слой | Технология |
|---|---|
| GUI | [PySide6](https://doc.qt.io/qtforpython/) (Qt для Python), кастомная тёмная тема через QSS |
| Компьютерное зрение | [OpenCV](https://opencv.org/) (захват видео) + [MediaPipe Tasks API](https://developers.google.com/mediapipe) (`PoseLandmarker`, `FaceLandmarker`) |
| Машинное обучение | [scikit-learn](https://scikit-learn.org/) (GradientBoosting / RandomForest, `GroupKFold`), `pandas`, `numpy` |
| Big Data | [PySpark](https://spark.apache.org/docs/latest/api/python/) через JDBC в SQLite |
| Хранилище | SQLite3 (паттерн Repository в `data/sqlite_repo.py`) |
| Отчётность | `matplotlib` (графики в памяти → `QPixmap`), `seaborn`, экспорт в PDF через `matplotlib.backends.backend_pdf` |
| Упаковка | PyInstaller (`ErgoBoost.spec`) |

## 🏗 Архитектура

```
Presentation (PySide6 GUI)  →  запускает QThread MonitoringWorker
        │
Services (CV + бизнес-логика)  →  PoseDetector, BlinkDetector, DistanceDetector,
        │                          BaselineCalibrator, BreakReminder, AlertManager
        ▼
Data Access (SQLite repository)  →  sessions, posture/eye/distance/presence events
        │
ML Pipeline  →  Predictor (инференс) + OnlineTrainer (фоновое дообучение) + PySpark (batch/big data)
```

GUI никогда не подвисает: вся работа с камерой и компьютерным зрением идёт в отдельном `QThread` (`MonitoringWorker`), общение с интерфейсом — исключительно через Qt signals/slots. Подробное описание каждого модуля и формулы (posture score, EAR, математика forward-shift и т.д.) — в [`architecture.md`](architecture.md).

## 🚀 Быстрый старт

**Требования:** Windows, Python 3.10+, веб-камера.

```bash
git clone https://github.com/SHOKinator/ErgoBoost-App.git
cd ErgoBoost-App

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt

python ergoboost_app.py
```

Всё — модели MediaPipe для позы/лица и предобученный классификатор осанки уже лежат в `models/` и `ml/models/`, докачивать ничего не нужно. При первом запуске вы создадите локальный аккаунт (хранится только в вашей локальной SQLite БД) и пройдёте короткую калибровку осанки.

<details>
<summary>Опционально: PySpark-пайплайн для больших данных</summary>

Компоненты PySpark (пакет `pyspark` + JDBC-драйвер `sqlite-jdbc` в `libs/`) нужны только если вы хотите запускать распределённые скрипты обучения/аналитики в `ml/train_pyspark.py` и `analytics/pyspark_analytics.py`. По умолчанию закомментированы в `requirements.txt`.
</details>

## 📁 Структура проекта

```
ergoboost/
├── ergoboost_app.py     # Точка входа
├── gui/                 # Окна PySide6, вкладки, поток мониторинга
├── services/             # CV-детекторы + бизнес-логика (поза, моргания, дистанция, калибровка, алерты, авторизация)
├── ml/                   # Инференс, online-дообучение, PySpark-пайплайн обучения, веса моделей
├── analytics/             # Сводная и PySpark-аналитика
├── data/                  # SQLite-репозиторий, схема, локальная БД (в .gitignore)
├── utils/                 # Графики, PDF-отчёты, логирование, экспорт в CSV
├── test/ & tools/          # Сбор датасетов, оценка модели, генерация синтетических данных
├── docs/                  # Документация по модулям + текст диплома
└── models/                # Предобученные модели MediaPipe для позы и лица
```

## 📊 Качество модели

Классификатор оценивается с групповой кросс-валидацией, чтобы избежать утечки данных между сессиями; полные метрики, матрицы ошибок и важность признаков генерируются `test/evaluate_model.py` и `ml/generate_diploma_charts.py`:

![Сравнение моделей](ml/diploma_charts/08_summary_table.png)

Больше графиков (матрицы ошибок, ROC-кривые, важность признаков, результаты кросс-валидации) — в [`ml/diploma_charts/`](ml/diploma_charts/) и [`test/results/`](test/results/).

## 📄 Дипломная работа

Полная методология, формулы и оценка результатов описаны в [`docs/diploma_paper.pdf`](docs/diploma_paper.pdf).

## ⚠️ Известные ограничения

- Нативные toast-уведомления (`winotify`) работают только на Windows.
- Оценка дистанции использует относительную ширину лица как прокси-метрику — глубины камеры нет, поэтому это эвристика, а не точное измерение.
- Для надёжного трекинга MediaPipe нужен достаточно освещённый, обращённый к камере кадр.

## 📝 Лицензия

MIT — см. [LICENSE](LICENSE).
