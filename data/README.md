# data/

Datos locales del proyecto. Esta carpeta no se commitea salvo README y plantillas.

Contenido esperado en Stage 0:

- `reference_clip/madrid_R1.mov`: clip Nivel A, local y no versionado.
- `reference_clip/manual_annotation.json`: eventos humanos de Stage 4 Nivel A.
- `clips/<clip_id>/source.mp4|mov`: fuente canonica local, ignorada por Git.
- `clips/<clip_id>/clip_manifest.json`: metadata e integridad versionables.
- `clips/<clip_id>/reference_frame.png`: frame derivado local, ignorado por Git.
- `reference_clip/reference_frame.png`: frame de referencia para calibracion.
- `reference_clip/manual_annotation.json`: anotacion manual Nivel A.

No guardar secretos ni tokens en esta carpeta.
