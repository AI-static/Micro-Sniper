# 推荐方案：Poetry 导出 + pip 安装

# 第一阶段：使用 Poetry 导出完整的 requirements.txt
# syntax=docker/dockerfile:1.7

############################
# 1) 导出 requirements.txt
############################
FROM python:3.12-slim AS req-generator

ARG DEBIAN_MIRROR=mirrors.ustc.edu.cn
ARG PYPI_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PYPI_TRUSTED=pypi.tuna.tsinghua.edu.cn

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=0 \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# 换源（兼容不同 slim 版本 sources 文件）
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    else \
      sed -i "s|deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list; \
    fi

RUN set -eux; \
    pip config set global.index-url "${PYPI_URL}"; \
    pip config set install.trusted-host "${PYPI_TRUSTED}"; \
    python -m pip install -U pip; \
    pip install poetry==2.0.0 poetry-plugin-export==1.9.0; \
    poetry config virtualenvs.create false

WORKDIR /app
COPY pyproject.toml poetry.lock* ./

# 导出：建议加 --with/--only/--without-hashes 根据你项目需要调整
RUN set -eux; \
    poetry export -f requirements.txt -o requirements.txt --without-hashes; \
    echo "=== 导出验证 ==="; \
    wc -l requirements.txt; \
    grep -E "(sanic|pydantic|httpx)" requirements.txt | head -5 || true


############################
# 2) 构建 wheel（可选但推荐）
############################
FROM python:3.12-slim AS wheel-builder

ARG DEBIAN_MIRROR=mirrors.ustc.edu.cn
ARG PYPI_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PYPI_TRUSTED=pypi.tuna.tsinghua.edu.cn

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    else \
      sed -i "s|deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list; \
    fi

# 只在 builder 装编译工具；runtime 不装（更小、更安全）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels
COPY --from=req-generator /app/requirements.txt /tmp/requirements.txt

RUN set -eux; \
    pip config set global.index-url "${PYPI_URL}"; \
    pip config set install.trusted-host "${PYPI_TRUSTED}"; \
    python -m pip install -U pip wheel; \
    pip wheel --wheel-dir /wheels -r /tmp/requirements.txt


############################
# 3) 运行时镜像（更轻量）
############################
FROM python:3.12-slim AS runtime

ARG DEBIAN_MIRROR=mirrors.ustc.edu.cn

ENV API_VERSION=v1.0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python \
    TZ=Asia/Shanghai \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    else \
      sed -i "s|deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list; \
    fi; \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime; \
    echo $TZ > /etc/timezone

WORKDIR /app

# 先安装依赖（利用 Docker layer cache）：只要 requirements 不变，这层能复用
COPY --from=wheel-builder /wheels /wheels
RUN set -eux; \
    python -m pip install -U pip; \
    pip install --no-index --find-links=/wheels /wheels/*.whl; \
    rm -rf /wheels

# 再复制业务代码（代码变更不会导致重装依赖）
COPY . .

# 非 root 用户
RUN set -eux; \
    adduser --uid 5678 --disabled-password --gecos "" appuser; \
    chown -R appuser:appuser /app; \
    # 给 site-packages 目录写权限 让 agentbay 可以写日志\
    chown -R appuser:appuser /usr/local/lib/python3.12/site-packages
USER appuser

CMD ["gunicorn", "-c", "config/gunicorn.py", "main:app"]


# 构建镜像
# docker build --platform linux/amd64 -t micro-sniper:latest .

# 运行容器
# docker run -d -p 8000:8000 --name micro-sniper micro-sniper:latest

# [debug] 运行容器（挂载代码目录 + 开启debug模式）
# docker run -d -p 8001:8000 -v .:/app -e APP_DEBUG=true -e APP_AUTO_RELOAD=true --name aether-debug aether:latest