FROM node:18.16 AS frontend_builder

WORKDIR /frontend

# Build arguments for frontend environment variables (embedded at build time)
ARG VITE_UI_THEME=dark

ENV VITE_UI_THEME=${VITE_UI_THEME}

COPY ./frontend/package.json ./frontend/yarn.lock ./

RUN yarn install --frozen-lockfile

COPY ./frontend/ ./

RUN echo "Building with theme: ${VITE_UI_THEME}" && yarn build


FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10-slim

WORKDIR /

ENV MAX_WORKERS=1

COPY ./backend/requirements.txt /tmp/

RUN pip install --no-cache-dir --upgrade -r /tmp/requirements.txt

COPY ./backend /app

COPY --from=frontend_builder /frontend/dist /app/frontend/dist
