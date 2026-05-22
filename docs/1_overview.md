# Архитектура и Документация Проекта ErgoBoost (Часть 1: Обзор и Структура)

## 1. Суть и Цель Проекта
**ErgoBoost** — это комплексное настольное приложение с элементами машинного обучения (Machine Learning) и компьютерного зрения (Computer Vision). Главная цель проекта: интеллектуальный мониторинг эргономики рабочего места пользователя (осанка, усталость глаз, расстояние до монитора, контроль перерывов) для сохранения здоровья при длительной работе за компьютером.

Приложение не просто использует набор жестких правил (Rule-based), но и поддерживает гибкие ML-предсказания (Random Forest / Gradient Boosting), дообучаясь на данных пользователя (Online Learning / Background Training), а также предоставляет глубокую аналитику через локальную базу данных (SQLite) и аналитические инструменты больших данных (PySpark).

## 2. Общая Архитектура
Система разделена на следующие ключевые слои:
1. **Presentation Layer (GUI)**: Реализован на базе `PySide6`. Работает в основном потоке. Обеспечивает интерфейс (Dashboard, Settings, Statistics) и системные функции (System Tray, Hotkeys, Screen Blur Overlay).
2. **Business Logic & Services (Services)**: Модули компьютерного зрения и оркестрации. Работают в фоновом потоке (`MonitoringWorker`). Анализируют кадры с вебкамеры.
3. **Data Access Layer (Data)**: Прямое взаимодействие с локальной базой данных SQLite (`sqlite_repo.py`). Отвечает за логирование метрик, управление сессиями, хранение настроек и исторических событий.
4. **Machine Learning Pipeline (ML)**: Компоненты для классификации осанки (`predictor.py`), горячего дообучения (`online_trainer.py`) и масштабного распределенного анализа данных (`pyspark_analytics.py`, `train_pyspark.py`).

## 3. Технологический Стек
- **Интерфейс:** `PySide6` (Qt for Python).
- **Компьютерное зрение:** `OpenCV` (захват видео), `MediaPipe` (Tasks API: `FaceLandmarker`, `PoseLandmarker`).
- **База Данных:** `SQLite3`.
- **Машинное Обучение:** `scikit-learn` (ML-модели: GradientBoostingClassifier, RandomForest), `PySpark` (распределенная аналитика), `pandas`, `numpy`.
- **Визуализация (Графики):** `matplotlib` (генерация графиков в памяти для GUI), `seaborn`.

## 4. Дерево Файлов и Структура Директорий
```
ergoboost/
├── ergoboost_app.py                # Точка входа в приложение. Настраивает пути, БД и запускает GUI.
├── requirements.txt                # Зависимости проекта.
├── config/
│   ├── settings.yaml               # Конфигурационный файл (переопределяется БД).
│   └── settings.py                 # Класс Settings: загрузка YAML и синхронизация с БД.
├── data/
│   ├── ergoboost.db                # SQLite БД (создается при запуске).
│   ├── schema.sql                  # Структура таблиц БД.
│   └── sqlite_repo.py              # Класс SQLiteRepository для всех операций с БД.
├── services/
│   ├── models_loader.py            # Загрузка легковесных моделей MediaPipe в память.
│   ├── pose_detector.py            # Вычисление отклонений осанки (наклоны головы/спины).
│   ├── blink_detector.py           # Вычисление EAR (Eye Aspect Ratio), детекция морганий.
│   ├── distance_detector.py        # Оценка расстояния от лица до монитора.
│   ├── baseline_calibrator.py      # Первоначальная калибровка пользователя (эталонная поза).
│   ├── break_reminder.py           # Учет времени работы и контроль отсутствия.
│   ├── alert_manager.py            # Вывод системных (Windows) уведомлений (через winotify).
│   ├── auth_service.py             # Регистрация, аутентификация (PBKDF2-SHA256).
│   ├── camera_service.py           # Обертка для OpenCV (VideoCapture).
│   └── session_manager.py          # Управление началом и концом сессии логирования.
├── gui/
│   ├── main_window.py              # Основное окно приложения, управление вкладками и TrayIcon.
│   ├── auth_window.py              # Окно логина/регистрации перед запуском main_window.
│   ├── monitoring_worker.py        # QThread Worker. Запускает цикл CV, собирает метрики со всех services.
│   ├── screen_overlay.py           # Затемнение экрана и таймер обратного отсчета при плохой позе.
│   ├── dashboard_tab.py            # Вкладка с видеопотоком и real-time метриками.
│   ├── statistics_tab.py           # Аналитика, тренды, генерация PDF-отчетов.
│   ├── sessions_tab.py             # Таблица исторических сессий.
│   ├── session_detail_dialog.py    # Подробные графики по конкретной исторической сессии.
│   ├── exercises_tab.py            # Текстовые инструкции по разминке.
│   └── settings_tab.py             # Интерфейс настройки параметров.
├── ml/
│   ├── models/                     # Папка с весами MediaPipe (.task) и ML-моделями (.pkl).
│   ├── predictor.py                # Инференс-класс (выдает предсказание OK/BAD по признакам).
│   ├── online_trainer.py           # Фоновый поток для переобучения модели (Online Learning).
│   ├── train_model.py              # Базовый скрипт обучения scikit-learn моделей на истории (batch train).
│   ├── train_posture_model.py      # Продвинутый скрипт обучения.
│   └── train_pyspark.py            # Spark-pipeline для распределенного обучения на огромных выборках.
├── analytics/
│   ├── analytics_service.py        # Простая генерация summary и JSON по историческим данным.
│   └── pyspark_analytics.py        # Использование PySpark для аналитики по дням и часам.
├── utils/
│   ├── logger.py, chart_utils.py, pdf_report.py, export_utils.py, etc. # Вспомогательные функции.
└── test/ & tools/                  # Скрипты тестирования, ручного сбора датасетов, mock-данных.
```
