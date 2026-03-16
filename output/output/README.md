# BackEnd-Archive

## Descripción General del Proyecto

El proyecto `BackEnd-Archive` es un servicio de gestión de archivos diseñado para manejar la subida, listado y descarga de documentos en un bucket de S3. Este servicio está integrado con un sistema de licenciamiento y gestión de usuarios (Comfama), permitiendo un control granular sobre los archivos archivados. Proporciona una API robusta para interactuar con el almacenamiento en la nube, facilitando operaciones clave para la administración de documentos.

## Tabla de Contenido
1. [Descripción General del Proyecto](#descripción-general-del-proyecto)
2. [Tabla de Contenido](#tabla-de-contenido)
3. [Tecnologías Utilizadas](#tecnologías-utilizadas)
4. [Configuración del Entorno](#configuración-del-entorno)
    - [Variables de Entorno](#variables-de-entorno)
5. [API Endpoints](#api-endpoints)
    - [Archivos](#archivos)
6. [Modelos de Datos (Schemas)](#modelos-de-datos-schemas)
7. [Instalación y Ejecución (Placeholder)](#instalación-y-ejecución-placeholder)
8. [Uso (Placeholder)](#uso-placeholder)
9. [Consideraciones Futuras (Placeholder)](#consideraciones-futuras-placeholder)

## Tecnologías Utilizadas

Aunque no se especifica explícitamente en los archivos proporcionados, la estructura de la API (OpenAPI 3.1.0) y la mención de `jdbc:mysql` sugieren un backend basado en Java/Spring Boot con una base de datos MySQL y almacenamiento en AWS S3.

## Configuración del Entorno

Para el correcto funcionamiento del servicio, se deben configurar las siguientes variables de entorno:

### Variables de Entorno

| Variable              | Descripción                                                                 | Valor de Ejemplo                                                              |
| :-------------------- | :-------------------------------------------------------------------------- | :---------------------------------------------------------------------------- |
| `AWS_NAME_BUCKET`     | Nombre del bucket de AWS S3 donde se almacenarán los archivos.              | `dev-gestorlicenciamiento-archive`                                            |
| `DB_PASSWORD`         | Contraseña para la conexión a la base de datos MySQL.                       | `Andr35%dev`                                                                  |
| `DB_USERNAME`         | Nombre de usuario para la conexión a la base de datos MySQL.                | `AndresArM`                                                                   |
| `URL_DB`              | URL de conexión a la base de datos MySQL.                                   | `jdbc:mysql://dbcomfamadigitaldev.csfppvl3wg8f.us-east-1.rds.amazonaws.com/GestorLicenciamiento` |

## API Endpoints

El servicio expone los siguientes endpoints para la gestión de archivos:

### Archivos

-   **`POST /files/upload`**
    -   **Descripción**: Sube un archivo a S3.
    -   **Parámetros de Query Requeridos**: `keyName`, `userComfamaId`, `userId`, `groupTypeId`, `licenceGroupId`, `productId`.
    -   **Cuerpo de la Solicitud**: Archivo binario (`file`).
    -   **Respuesta**: Nombre del archivo subido y mensaje de éxito.

-   **`GET /files/list/archive/active`**
    -   **Descripción**: Lista archivos activos en S3 con filtros y paginación.
    -   **Parámetros de Query Opcionales**: `fechaInicio`, `fechaFin`, `groupTypeId` (array), `userComfamaName`, `stateId`, `page` (default 1).
    -   **Respuesta**: Lista paginada de `FileHistoryResponseDto`.

-   **`GET /files/downloadFileWithErrors`**
    -   **Descripción**: Descarga un archivo desde S3.
    -   **Parámetros de Query Requeridos**: `keyName` (nombre del archivo con extensión, e.g., `fileEstructura-95.xlsx`).
    -   **Respuesta**: Archivo binario.

## Modelos de Datos (Schemas)

Los siguientes DTOs (Data Transfer Objects) son utilizados en las respuestas de la API:

-   **`ApiResponseString`**: Estructura genérica para respuestas de API con un mensaje y datos de tipo String.
-   **`FileHistoryResponseDto`**: Representa el historial de un archivo, incluyendo `id`, `name`, `saveDate`, `state`, `successful`, `isProcessing`, `userComfamaId`, `fileTypeId`, `fileUrl`, `user`, `groupType`, `licenceGroup`, `product`, `rowProcess`.
-   **`GroupTypeDto`**: Contiene `id` y `name` para un tipo de grupo.
-   **`LicenceGroupDto`**: Contiene `id` y `name` para un grupo de licencia.
-   **`PaginatedApiResponseFileHistoryResponseDto`**: Respuesta paginada que contiene una lista de `FileHistoryResponseDto` y metadatos de paginación.
-   **`PaginationDto`**: Contiene `page`, `totalPages`, `pageSize`, `totalRecords` para la paginación.
-   **`ProductDto`**: Contiene `id`, `name`, `shortName` para un producto.
-   **`StateDto`**: Contiene `id`, `name`, `stateColor` para un estado.
-   **`UserDto`**: Contiene `id` y `name` para un usuario.

## Instalación y Ejecución (Placeholder)

_Esta sección requiere información adicional sobre cómo compilar y ejecutar el proyecto. Típicamente incluiría pasos como clonar el repositorio, instalar dependencias (Maven/Gradle), configurar la base de datos y ejecutar el servicio._

## Uso (Placeholder)

_Esta sección detallaría cómo interactuar con la API utilizando herramientas como cURL, Postman o un cliente HTTP programático, mostrando ejemplos de solicitudes y respuestas para cada endpoint._

## Consideraciones Futuras (Placeholder)

_Posibles mejoras o características a considerar en el futuro, como autenticación/autorización más robusta, logging avanzado, monitoreo, integración con otros servicios, etc._
