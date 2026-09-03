# Qiniu QVS Notifier

[简体中文](../README.md) | [English](README.en.md) | [Español](README.es.md) | [Français](README.fr.md)

Supervisión de dispositivos Qiniu QVS con alertas cuando cambia el estado mediante DingTalk u otro webhook. El panel Web y el monitor en segundo plano comparten el núcleo de supervisión, la configuración y el almacenamiento SQLite.

## Instalación

### Docker: Usar imagen preconstruida (Recomendado)

```bash
docker run -d \
  -p 8000:8000 \
  -v ./config:/app/config \
  --restart always \
  --name qiniu-qvs-notifier \
  ghcr.io/katfionn/qiniu-qvs-notifier:latest
```

Abra `http://localhost:8000` para configurar.

### Docker: Construir desde el código fuente

Docker ofrece exclusivamente el servicio Web; no incluye la TUI interactiva ni la selección de modo de servicio.

```bash
docker compose up -d --build
```

Abra `http://localhost:8000`. El directorio montado `./config` conserva la configuración y los dispositivos. `restart: always` recupera el servicio después de fallos y reinicios del host.

### Código fuente: instalador y gestor TUI

Use Python 3.9 o posterior:

```bash
python install.py
```

El punto de entrada comprueba las dependencias y puede instalar `requirements.txt`; después abre la TUI. Elija un modo:

- **Servicio Web**: ejecuta el panel y el monitor integrado en `http://127.0.0.1:8000`.
- **Servicio TUI/monitor**: ejecuta únicamente el monitor no interactivo en segundo plano. La TUI sigue siendo una herramienta de gestión en primer plano.

La TUI permite instalar, consultar estado, iniciar, detener, reiniciar, ver el comando de registros, configurar, elegir idioma y desinstalar. Los servicios existentes se gestionan sin duplicarlos.

## Servicios nativos y desinstalación

En Linux, el instalador crea una unidad systemd dinámica con `WorkingDirectory`, `ExecStart`, `Restart=on-failure` y `systemctl enable`; use `sudo` para modificar servicios.

En Windows, pywin32 `ServiceFramework` registra un servicio real de Windows. Se necesitan privilegios de administrador y la política de recuperación reinicia los servicios que fallen.

Seleccione **Uninstall Qiniu QVS Notifier** en la TUI. Tras dos confirmaciones elimina el servicio nativo y el inicio automático, y permite conservar o eliminar `config/` (credenciales y datos de dispositivos).

## Idiomas

Este README está disponible en chino simplificado, inglés, español y francés; el chino es el idioma predeterminado.

La aplicación ofrece actualmente chino simplificado (`zh-CN`) e inglés (`en-US`) en instalador, TUI, mensajes de servicio/API e interfaz Web. La elección se guarda en `config/settings.yaml`.

## Desarrollo

Use `python run_web.py --reload` solo para desarrollo Web local. Los servicios de producción y Docker no usan modo reload.
