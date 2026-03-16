# BackEnd-Notification

## Descripción General

Este proyecto es un servicio de backend diseñado para la gestión y envío masivo de notificaciones a través de correo electrónico y WhatsApp. Facilita la comunicación automatizada al integrar con servicios externos de mensajería y permite la configuración dinámica de plantillas mediante códigos internos almacenados en una base de datos.

## Características Principales

*   **Envío Masivo de WhatsApp:** Capacidad para enviar mensajes de WhatsApp a múltiples destinatarios de forma simultánea.
*   **Envío Masivo de Correo Electrónico:** Funcionalidad para enviar correos electrónicos masivos, utilizando plantillas configurables dinámicamente.
*   **Personalización de Mensajes:** Soporte para la inclusión de parámetros personalizados en los mensajes de correo y WhatsApp, permitiendo una comunicación adaptada a cada destinatario.
*   **Configuración Dinámica:** Utiliza un "InternalCode" para obtener configuraciones de plantillas de correo desde la base de datos (`AppSettings`), lo que permite una gran flexibilidad sin necesidad de cambios en el código.
*   **Integración con Servicios Externos:** Conexión con APIs de WhatsApp y servicios de envío de correo electrónico.

## Tecnologías Utilizadas (Inferidas)

*   **Lenguaje de Programación:** Java (comúnmente asociado con la generación de `api-docs.json` por Springdoc/OpenAPI).
*   **Framework:** Spring Boot (sugerido por la estructura de la API y el uso de `localhost:7004`).
*   **Base de Datos:** MySQL (indicado por la URL de conexión `URL_DB` en las variables de entorno).
*   **Documentación de API:** OpenAPI 3.1.0.

## Estructura del Proyecto

El proyecto incluye los siguientes archivos y documentos importantes:

*   `api-docs.json`: La especificación OpenAPI que describe todos los endpoints, modelos de datos y operaciones de la API de notificación.
*   `Documentacion.Notification.docx`: Documento de Word que probablemente contiene la documentación funcional o técnica detallada del proyecto.
*   `Notification Comfama - SWAT.docx`: Documento de Word que podría contener un análisis SWAT (Fortalezas, Oportunidades, Debilidades, Amenazas) o un análisis similar del proyecto.
*   `variables-notification.txt`: Un archivo que contiene variables de entorno críticas y configuraciones sensibles, como credenciales de base de datos y claves de API.

## Configuración del Entorno

El archivo `variables-notification.txt` contiene las variables de entorno necesarias para el correcto funcionamiento de la aplicación. Es crucial configurar estas variables de forma segura en el entorno de despliegue (por ejemplo, como variables de entorno del sistema o utilizando un archivo `.env` si el framework lo soporta).

A continuación, se listan las variables identificadas:

*   `AUTHORIZATION_WHATSAPP`: Token de autorización Basic para la API de WhatsApp.
*   `COOKIE_TOKENIZER`: Cookie utilizada para el servicio de tokenización.
*   `DB_PASSWORD`: Contraseña para la conexión a la base de datos MySQL.
*   `DB_USERNAME`: Nombre de usuario para la conexión a la base de datos MySQL.
*   `KEY_TOKENIZER`: Clave para el servicio de tokenización general.
*   `KEY_TOKENIZER_EMAIL`: Clave específica para el servicio de tokenización de correo electrónico.
*   `URL_COMFAMA_QA`: URL base para el entorno de QA de Comfama.
*   `URL_DB`: URL de conexión JDBC para la base de datos MySQL (ej. `jdbc:mysql://dbcomfamadigitaldev.csfppvl3wg8f.us-east-1.rds.amazonaws.com/GestorLicenciamiento`).
*   `URL_EMAIL_NOTIFICACION`: Endpoint para el servicio de envío de correos masivos.
*   `URL_TOKENIZER`: Endpoint para el servicio de tokenización.
*   `URL_WHATSAPP`: Endpoint para la API de WhatsApp.

## Endpoints de la API

La API de Notificaciones expone los siguientes endpoints:

### 1. `POST /notification/enviar/whatsapp`

*   **Resumen:** Envía mensajes de WhatsApp de forma masiva.
*   **Descripción:** Permite el envío de mensajes de WhatsApp a múltiples destinatarios, incluyendo todos los parámetros necesarios en el cuerpo de la solicitud.
*   **Tags:** Notification
*   **Cuerpo de la Solicitud (Request Body):**
    *   Tipo: `application/json`
    *   Schema: Array de objetos `WhatsAppRequest`
    *   **Ejemplo:**
        ```json
        [
          {
            "ListId": 305,
            "Phone": "57300XXXXXXX",
            "Param1": "Nombre persona de envio",
            "Param2": "correo_persona_envia@comfama.com.co",
            "DynamicUrlData1": "correo_persona_envia@comfama.com.co"
          }
        ]
        ```
*   **Respuestas:**
    *   `200 OK`: Mensajes de WhatsApp enviados exitosamente.
    *   `400 Bad Request`: Datos de entrada inválidos.
    *   `500 Internal Server Error`: Error interno del servidor.

### 2. `POST /notification/enviar/recipients`

*   **Resumen:** Envía correo masivo con recipients únicamente.
*   **Descripción:** Envía un correo electrónico masivo proporcionando solo la lista de destinatarios y un `InternalCode`. Los demás campos de configuración del correo (como el `templateId`) se obtienen automáticamente desde la base de datos (`AppSettings`) utilizando el `InternalCode`.
*   **Tags:** Notification
*   **Cuerpo de la Solicitud (Request Body):**
    *   Tipo: `application/json`
    *   Schema: Objeto `RecipientsOnlyRequest`
    *   **Ejemplo:**
        ```json
        {
          "InternalCode": "301",
          "Recipients": [
            {
              "To": "leonardmartinez.contratista@comfama.com.co",
              "Parameters": [
                {
                  "Name": "Nombre",
                  "Type": "text",
                  "Value": "Marcela"
                },
                {
                  "Name": "Correo",
                  "Type": "text",
                  "Value": "leonardmartinez.contratista@comfama.com.co"
                },
                {
                  "Name": "Meses",
                  "Type": "text",
                  "Value": "1"
                }
              ]
            }
          ]
        }
        ```
*   **Respuestas:**
    *   `200 OK`: Correo enviado exitosamente.
    *   `400 Bad Request`: Datos de entrada inválidos.
    *   `500 Internal Server Error`: Error interno del servidor.

## Modelos de Datos (Schemas)

### `WhatsAppRequest`

Objeto que representa los detalles de un mensaje de WhatsApp a enviar.

| Propiedad        | Tipo     | Descripción                               | Requerido | Ejemplo                               |
| :--------------- | :------- | :---------------------------------------- | :-------- | :------------------------------------ |
| `ListId`         | `string` | Identificador de la lista de envío.       | Sí        | `305`                                 |
| `Phone`          | `string` | Número de teléfono del destinatario.      | Sí        | `57300XXXXXXX`                        |
| `Param1`         | `string` | Primer parámetro personalizable.          | Sí        | `Nombre persona de envio`             |
| `Param2`         | `string` | Segundo parámetro personalizable.         | Sí        | `correo_persona_envia@comfama.com.co` |
| `DynamicUrlData1`| `string` | Datos dinámicos para la URL (opcional).   | No        | `correo_persona_envia@comfama.com.co` |
| `URL`            | `string` | URL asociada al mensaje (opcional).       | No        | `https://example.com`                 |

### `ApiResponseObject`

Objeto de respuesta estándar para las operaciones de la API.

| Propiedad   | Tipo      | Formato     | Descripción                               |
| :---------- | :-------- | :---------- | :---------------------------------------- |
| `status`    | `integer` | `int32`     | Código de estado de la respuesta.         |
| `message`   | `string`  |             | Mensaje descriptivo de la respuesta.      |
| `data`      | `object`  |             | Datos adicionales de la respuesta.         |
| `timestamp` | `string`  | `date-time` | Marca de tiempo de la respuesta.          |
| `path`      | `string`  |             | Ruta de la solicitud que generó la respuesta.|

### `Parameter`

Objeto que representa un parámetro personalizable para una plantilla de correo electrónico.

| Propiedad | Tipo     | Descripción                               | Requerido | Ejemplo   |
| :-------- | :------- | :---------------------------------------- | :-------- | :-------- |
| `Name`    | `string` | Nombre del parámetro (ej. "Nombre").      | Sí        | `Nombre`  |
| `Type`    | `string` | Tipo del parámetro (ej. "text").          | Sí        | `text`    |
| `Value`   | `string` | Valor del parámetro (ej. "Sebastian").    | Sí        | `Sebastian` |

### `Recipient`

Objeto que contiene la información de un destinatario de correo electrónico y sus parámetros personalizados.

| Propiedad    | Tipo               | Descripción                               | Requerido | Ejemplo                                   |
| :----------- | :----------------- | :---------------------------------------- | :-------- | :---------------------------------------- |
| `To`         | `string`           | Dirección de correo electrónico del destinatario.| Sí        | `leonardmartinez.contratista@comfama.com.co` |
| `Parameters` | `array` de `Parameter` | Lista de parámetros personalizados para la plantilla.| No        | `[{"Name":"Nombre", "Type":"text", "Value":"Marcela"}]` |

### `RecipientsOnlyRequest`

Objeto de solicitud para el envío de correo masivo que solo requiere el código interno y la lista de destinatarios.

| Propiedad      | Tipo               | Descripción                               | Requerido | Ejemplo   |
| :------------- | :----------------- | :---------------------------------------- | :-------- | :-------- |
| `InternalCode` | `string`           | Código interno para obtener la configuración del template desde la tabla `AppSettings`.| Sí        | `301`     |
| `Recipients`   | `array` de `Recipient` | Lista de destinatarios del correo, cada uno con su email y parámetros personalizados.| Sí        | `[{"To":"...", "Parameters": [...]}]` |

## Cómo Ejecutar el Proyecto (Guía General)

Dado que este es un proyecto de backend, los pasos generales para su ejecución serían:

1.  **Prerrequisitos:**
    *   Java Development Kit (JDK) (versión compatible con el proyecto).
    *   Maven o Gradle (herramienta de construcción, si es un proyecto Java).
    *   Acceso a una instancia de base de datos MySQL con las credenciales y esquemas configurados según `URL_DB`.
2.  **Clonar el Repositorio:** Obtén el código fuente del proyecto desde tu sistema de control de versiones.
    ```bash
    git clone <URL_DEL_REPOSITORIO>
    cd BackEnd-Notification
    ```
3.  **Configurar Variables de Entorno:** Asegúrate de que todas las variables listadas en la sección "Configuración del Entorno" estén correctamente establecidas en tu sistema o en un archivo `.env` si tu configuración lo permite.
4.  **Construir el Proyecto:** Utiliza tu herramienta de construcción para compilar el proyecto y generar el artefacto ejecutable (normalmente un archivo `.jar`).
    ```bash
    # Si usas Maven
    mvn clean install
    # Si usas Gradle
    gradle build
    ```
5.  **Ejecutar la Aplicación:** Una vez construido, puedes ejecutar la aplicación.
    ```bash
    java -jar target/<nombre-del-artefacto>.jar
    ```
    (Reemplaza `<nombre-del-artefacto>.jar` con el nombre real del archivo JAR generado).

La aplicación debería iniciarse y estar disponible en la URL configurada, por ejemplo, `http://localhost:7004/notification`.

## Documentación Adicional

Para obtener información más detallada sobre el proyecto, consulta los siguientes documentos:

*   `Documentacion.Notification.docx`
*   `Notification Comfama - SWAT.docx`

## Contacto y Soporte

Para cualquier pregunta o soporte, por favor contacta al equipo de desarrollo.
