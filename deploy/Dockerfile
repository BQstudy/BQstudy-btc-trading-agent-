# BTC交易Agent Docker镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目代码
COPY src/ ./src/
COPY config/ ./config/

# 创建必要的目录
RUN mkdir -p data logs reports

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 暴露端口（用于健康检查）
EXPOSE 8080

# 启动命令
CMD ["python", "src/agent.py", "--paper", "--interval", "3600"]
