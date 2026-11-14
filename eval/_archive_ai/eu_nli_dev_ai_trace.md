# Trazabilidad y justificación por par — PROPUESTAS IA PROVISIONALES

gold: false · ai_proposals_only: true · review_status global: pending-human-review + pending-independent-review

PROHIBIDO usar estas propuestas para calibrar umbrales, puntuar el modelo NLI o como prueba reservada.
Cada par propone UNA etiqueta (supported | contradicted | unsupported) a partir del fragmento citado;
la etiqueta solo será válida tras revisión independiente y humana (ver eval/EU_CORPUS.md).
Fuentes: PDF verificados por SHA-256 contra eval/eu_manifest.yaml; solo split dev; solo cuerpo editorial UE;
elementos de terceros (fotos, pies con ©) excluidos. Extracción pypdfium2 + troceado 800/120 de Ragmur.
Canon de literalidad: colapso \s+ -> un espacio; ligaduras y artefactos conservados;
viñetas y marcadores (• ‣ → > ‒ :) reproducidos exactos; normalizaciones documentadas en cada nota.

## eu-dev-001 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: El presupuesto europeo · document_id 186d5adb… · split dev · página 1 · chunk 1 · rights p.2 (CC BY 4.0) · sha256 883cb0084f27bb9c…
- Fenómenos: ninguno
- Motivo de la propuesta: Paráfrasis fiel de la premisa, sin cifras ni negación.
- Premisa: Las personas y las empresas se sitúan en el núcleo de las inversiones en la transición limpia.
- Afirmación: Las inversiones en la transición limpia ponen a las personas y a las empresas en el centro.

## eu-dev-002 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: El presupuesto europeo · document_id 186d5adb… · split dev · página 2 · chunk 3 · rights p.2 (CC BY 4.0) · sha256 883cb0084f27bb9c…
- Fenómenos: numeric
- Motivo de la propuesta: Comparación entre dos cifras de la misma tabla; el 70 % es el máximo.
- Premisa: PROGRAMAS METAS Planes de colaboración nacional y regional 43 % Fondo Europeo de Competitividad 43 % Programa Marco de Investigación e Innovación 40 % Mecanismo «Conectar Europa» 70 % Instrumento Europa Global 30 %
- Afirmación: El Mecanismo «Conectar Europa» tiene la meta más alta de la tabla, un 70 %, frente al 30 % del Instrumento Europa Global.

## eu-dev-003 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: El presupuesto europeo · document_id 186d5adb… · split dev · página 1 · chunk 2 · rights p.2 (CC BY 4.0) · sha256 883cb0084f27bb9c…
- Fenómenos: negation
- Motivo de la propuesta: La premisa exige garantizar que NO causen perjuicio; la afirmación lo permite. Negación en la premisa.
- Premisa: El principio de «no causar un perjuicio significativo»: ‒ debe aplicarse mediante un enfoque único, sencillo y proporcionado, garantizando que las actividades financiadas por la UE no causen un perjuicio significativo a 
- Afirmación: Las actividades financiadas por la UE pueden causar un perjuicio significativo a los objetivos climáticos sin ninguna restricción.

## eu-dev-004 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 4 · chunk 13 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: negation
- Motivo de la propuesta: La premisa limita los límites a DABIS («solo»); la afirmación los extiende a la ayuda asociada. Alcance contradictorio con negación en la premisa.
- Premisa: Es importante señalar que estos límites solo se aplican a DABIS, sin que se vean afectadas otras formas de ayuda, como las ayudas a la renta asociadas, los programas de inversión o las medidas agroambientales y climática
- Afirmación: Estos límites también se aplican a las ayudas a la renta asociada.

## eu-dev-005 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: El presupuesto europeo · document_id 186d5adb… · split dev · página 2 · chunk 5 · rights p.2 (CC BY 4.0) · sha256 883cb0084f27bb9c…
- Fenómenos: ninguno
- Motivo de la propuesta: Sede y plantilla no mencionadas; compatible con la premisa pero no inferible de ella.
- Premisa: El Banco de Descarbonización Industrial, anunciado en el Pacto por una Industria Limpia, se integrará en la gobernanza del Fondo de Competitividad.
- Afirmación: El Banco de Descarbonización Industrial tiene su sede en Bruselas y emplea a más de cien personas.

## eu-dev-006 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: El presupuesto europeo · document_id 186d5adb… · split dev · página 2 · chunk 6 · rights p.2 (CC BY 4.0) · sha256 883cb0084f27bb9c…
- Fenómenos: coreference
- Motivo de la propuesta: «Dicho mecanismo» remite a la premisa; el informe anual no se menciona. Compatible pero no inferible.
- Premisa: El Mecanismo «Conectar Europa» impulsará las inversiones en proyectos de infraestructuras transfronterizas clave en los sectores de la energía y el transporte, que son cruciales para completar la Unión de la Energía y la
- Afirmación: Dicho mecanismo publicará cada año un informe con el número exacto de pasos fronterizos modernizados.

## eu-dev-007 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Misión de la UE: restaurar nuestro océano y nuestras aguas · document_id 06b9b2a8… · split dev · página 1 · chunk 0 · rights p.3 (CC BY 4.0) · sha256 61885815ef16f9c6…
- Fenómenos: ninguno
- Motivo de la propuesta: Paráfrasis fiel; sin cifras, negación ni correferencia.
- Premisa: Establecen objetivos claros y delimitados en el tiempo y reúnen a los investigadores, los responsables políticos y las partes interesadas con el fin de impulsar la innovación y ofrecer soluciones concretas en beneficio d
- Afirmación: Las misiones fijan objetivos concretos con plazos y reúnen a investigadores, responsables políticos y partes interesadas para impulsar la innovación.

## eu-dev-008 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Misión de la UE: restaurar nuestro océano y nuestras aguas · document_id 06b9b2a8… · split dev · página 1 · chunk 3 · rights p.3 (CC BY 4.0) · sha256 61885815ef16f9c6…
- Fenómenos: numeric
- Motivo de la propuesta: Dos cifras (1 000 acciones, 7 700 millones) conservadas en la paráfrasis.
- Premisa: Ya se han aprobado más de 1 000 acciones en el marco de la Carta de la Misión para la restauración de los océanos, con el apoyo de un presupuesto de más de 7 700 millones de euros.
- Afirmación: La Carta de la Misión reúne más de un millar de acciones respaldadas por más de 7 700 millones de euros.

## eu-dev-009 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Misión de la UE: restaurar nuestro océano y nuestras aguas · document_id 06b9b2a8… · split dev · página 2 · chunk 6 · rights p.3 (CC BY 4.0) · sha256 61885815ef16f9c6…
- Fenómenos: numeric
- Motivo de la propuesta: La premisa sitúa el pleno funcionamiento en 2030; la afirmación lo adelanta a 2025. Fecha contradictoria.
- Premisa: Se espera que la plataforma alcance su pleno funcionamiento de aquí a 2030.
- Afirmación: La plataforma ya alcanzó su pleno funcionamiento en 2025.

## eu-dev-010 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Misión de la UE: restaurar nuestro océano y nuestras aguas · document_id 06b9b2a8… · split dev · página 1 · chunk 2 · rights p.3 (CC BY 4.0) · sha256 61885815ef16f9c6…
- Fenómenos: negation,numeric
- Motivo de la propuesta: La premisa afirma cuatro faros; la afirmación los niega. Sin alterar cifras en la afirmación.
- Premisa: Para acelerar los avances hacia la consecución de los objetivos de la misión, se han puesto en marcha cuatro Faros de la Misión a modo de centros regionales.
- Afirmación: No se ha puesto en marcha ningún Faro de la Misión como centro regional.

## eu-dev-011 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Misión de la UE: restaurar nuestro océano y nuestras aguas · document_id 06b9b2a8… · split dev · página 1 · chunk 3 · rights p.3 (CC BY 4.0) · sha256 61885815ef16f9c6…
- Fenómenos: numeric
- Motivo de la propuesta: Observadores de Oceanía no mencionados; compatible pero no inferible. Se conservan las cifras de la premisa.
- Premisa: Esto incluye compromisos por parte de 179 países más de cincuenta regiones y noventa municipios, a los que siguen sumándose otros.
- Afirmación: Entre los firmantes hay también observadores de países de Oceanía.

## eu-dev-012 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Misión de la UE: restaurar nuestro océano y nuestras aguas · document_id 06b9b2a8… · split dev · página 2 · chunk 4 · rights p.3 (CC BY 4.0) · sha256 61885815ef16f9c6…
- Fenómenos: coreference
- Motivo de la propuesta: «Este apoyo» remite a la premisa; construir puertos no se menciona. Compatible pero no inferible.
- Premisa: La misión presta apoyo directo a las comunidades clave a través de evaluaciones técnicas y estudios de viabilidad a medida para puertos, pesquerías y comunidades insulares, así como servicios de asesoramiento financiero 
- Afirmación: Este apoyo directo a las comunidades incluye también la construcción de nuevos puertos comerciales.

## eu-dev-013 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Misión de la UE: restaurar nuestro océano y nuestras aguas · document_id 06b9b2a8… · split dev · página 3 · chunk 7 · rights p.3 (CC BY 4.0) · sha256 61885815ef16f9c6…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa afirma impulsar ambas transiciones; la afirmación invierte la relación sin negación literal.
- Premisa: Además, contribuye a la prosperidad y la competitividad sostenibles de Europa al impulsar las transiciones ecológica y digital en estos ecosistemas vitales.
- Afirmación: La misión frena las transiciones ecológica y digital para proteger la competitividad europea.

## eu-dev-014 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Misión de la UE: restaurar nuestro océano y nuestras aguas · document_id 06b9b2a8… · split dev · página 2 · chunk 5 · rights p.3 (CC BY 4.0) · sha256 61885815ef16f9c6…
- Fenómenos: numeric
- Motivo de la propuesta: Cifras 2022 y 15 millones más enumeración de usuarios; sin equivalencia externa de la sigla.
- Premisa: La EU DTO, puesta en marcha en 2022 con una financiación anual de 15 millones de euros, tiene por objeto proporcionar conocimientos sobre los océanos accesibles y de base científica a una gran variedad de usuarios, desde
- Afirmación: La EU DTO se financia con 15 millones de euros anuales desde 2022 y sus usuarios incluyen a responsables políticos, investigadores, empresas, activistas y ciudadanos.

## eu-dev-015 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 2 · chunk 5 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: ninguno
- Motivo de la propuesta: Paráfrasis fiel; el alcance (varios regímenes actuales) se conserva.
- Premisa: DABIS sustituye a varios regímenes de ayuda existentes en la PAC en la actualidad, combinándolos y simplifcándolos.
- Afirmación: La nueva ayuda DABIS reemplaza y simplifica varios regímenes de ayuda de la PAC actual.

## eu-dev-016 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 3 · chunk 10 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: numeric
- Motivo de la propuesta: Cifra 3 000 EUR y alcance (todos los Estados miembros) conservados.
- Premisa: Además, todos los Estados miembros deben ofrecer a las explotaciones más pequeñas la opción de un pago anual de hasta 3 000 EUR.
- Afirmación: Las explotaciones más pequeñas tienen derecho a optar por un pago anual de hasta 3 000 euros en todos los Estados miembros.

## eu-dev-017 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 3 · chunk 8 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: ninguno
- Motivo de la propuesta: Paráfrasis fiel; sin cifras, negación ni correferencia.
- Premisa: En consonancia con la Estrategia de relevo generacional, se anima a los Estados miembros a duplicar la fnanciación de la PAC destinada a los jóvenes agricultores, haciendo hincapié en la importancia de la inversión.
- Afirmación: Se pide a los Estados miembros que dupliquen los fondos de la PAC para jóvenes agricultores dentro de la estrategia de relevo generacional.

## eu-dev-018 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 6 · chunk 20 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: numeric
- Motivo de la propuesta: Horquilla numérica conservada en la paráfrasis.
- Premisa: La ayuda media a nivel nacional en virtud de la ayuda decreciente a la renta por superfcie oscilará entre 130 y 240 EUR por hectárea.
- Afirmación: La ayuda media nacional por superficie se situará en una horquilla de 130 a 240 euros por hectárea.

## eu-dev-019 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 3 · chunk 6 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: negation
- Motivo de la propuesta: La premisa enumera a las mujeres entre los destinatarios; la afirmación las excluye. Alcance contradictorio con negación en la afirmación.
- Premisa: DABIS se destina a apoyar, en particular: • Agricultores activos • Jóvenes y nuevos agricultores • Mujeres agricultoras • Explotaciones familiares y pequeñas • Explotaciones mixtas (cultivo y cría de ganado) • Explotacio
- Afirmación: Las mujeres agricultoras quedan excluidas de los destinatarios de la ayuda DABIS.

## eu-dev-020 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 6 · chunk 20 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: coreference
- Motivo de la propuesta: «Estos límites» remite a la horquilla 130-240 de la frase anterior; la premisa afirma homogeneidad y la afirmación, aumento de diferencias.
- Premisa: Estos límites inferior y superior garantizan que las diferencias entre la ayuda media por hectárea para los pagos directos sean más homogéneas entre los Estados miembros.
- Afirmación: Los límites aumentan las diferencias entre Estados miembros.

## eu-dev-021 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 3 · chunk 10 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: ninguno
- Motivo de la propuesta: Antónimos voluntaria/obligatoria; contradicción sin negación literal en ninguna de las dos frases.
- Premisa: La participación de los agricultores en el régimen será voluntaria.
- Afirmación: La participación de los agricultores en el régimen es obligatoria.

## eu-dev-022 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 4 · chunk 14 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: numeric
- Motivo de la propuesta: Porcentaje distinto (25 % frente a 50 %). Contradicción numérica.
- Premisa: De 50 000 a 75 000 Reducción del 50 % en la horquilla de 50 000 a 75 000 EUR
- Afirmación: En la horquilla de 50 000 a 75 000 euros se aplica una reducción del 25 %.

## eu-dev-023 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 1 · chunk 2 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: numeric
- Motivo de la propuesta: Activación en 2026 y motivo concreto no mencionados; compatible con la premisa pero no inferible.
- Premisa: Además, una Red de Seguridad para la Unidad (‘Unity Safety Net’) de 6 300 millones EUR durante el período 2028-2034 contribuirá a estabilizar los mercados agrícolas en caso de perturbaciones del mercado.
- Afirmación: La Red de Seguridad se activó ya en 2026 ante una crisis de precios de los cereales.

## eu-dev-024 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 2 · chunk 3 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: ninguno
- Motivo de la propuesta: Complemento para apicultores no mencionado; compatible pero no inferible. Viñetas unidas con comas.
- Premisa: Presupuesto específco para la ayuda a la renta ‣ Ayuda decreciente a la renta por superfcie* ‣ Ayuda a la renta asociada* ‣ Pago específco al cultivo del algodón* ‣ Pago para zonas con limitaciones naturales u otras limi
- Afirmación: La ayuda a la renta asociada incluye un complemento específico para apicultores de montaña.

## eu-dev-025 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 6 · chunk 19 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: «Este porcentaje» remite a la premisa; la revisión bienal no se menciona. Compatible pero no inferible.
- Premisa: Los Estados miembros pueden asignar a intervenciones de ayuda a la renta asociada hasta el 20 % de las contribuciones de la Unión a la ayuda decreciente a la renta por superfcie, al pago específco al cultivo de algodón, 
- Afirmación: Este porcentaje máximo del 20 % se revisa cada dos años por el Consejo.

## eu-dev-026 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: El presupuesto de Europa · document_id 2acad822… · split dev · página 7 · chunk 21 · rights p.8 (CC BY 4.0) · sha256 4afc822dea51a1f0…
- Fenómenos: numeric
- Motivo de la propuesta: Destino concreto no mencionado; compatible pero no inferible.
- Premisa: Además, los agricultores en transición hacia métodos agrícolas más sostenibles pueden optar a recibir montos únicos de hasta 200 000 EUR.
- Afirmación: Estos montos únicos también cubren la compra de maquinaria pesada diésel.

## eu-dev-027 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 1 · chunk 2 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: numeric
- Motivo de la propuesta: Fecha y órganos conservados en la paráfrasis.
- Premisa: En abril de 2017, el Parlamento Europeo y el Consejo adoptaron el Reglamento sobre productos sanitarios (UE) 2017/745 (MDR) y el Reglamento sobre productos sanitarios para diagnóstico in vitro (UE) 2017/746 (IVDR).
- Afirmación: Los Reglamentos MDR e IVDR fueron adoptados en abril de 2017 por el Parlamento Europeo y el Consejo.

## eu-dev-028 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 1 · chunk 3 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: numeric
- Motivo de la propuesta: Dos fechas de entrada en vigor conservadas.
- Premisa: El Reglamento MDR entró en vigor el 26 de mayo de 2021. El IVDR sustituyó a la Directiva sobre productos sanitarios para diagnóstico in vitro (98/79/CE) (IVDD). El Reglamento IVDR entró en vigor el 26 de mayo de 2022.
- Afirmación: El MDR se aplica desde el 26 de mayo de 2021 y el IVDR desde el 26 de mayo de 2022.

## eu-dev-029 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 2 · chunk 7 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: ninguno
- Motivo de la propuesta: Alcance (todos los demás) y consecuencia conservados en la paráfrasis.
- Premisa: Todos los demás productos necesitan un certificado expedido por un organismo notificado; en ese caso, la marca CE va seguida del número del organismo notificado.
- Afirmación: Salvo los de menor riesgo, los productos requieren certificado de un organismo notificado y su marca CE incluye el número de dicho organismo.

## eu-dev-030 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 3 · chunk 23 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: ninguno
- Motivo de la propuesta: Obligación, productos y base jurídica conservados.
- Premisa: Todos los operadores económicos deberán almacenar y conservar los UDIs de los productos implantables de la clase III que hayan vendido o recibido, según lo dispuesto en el artículo 27, apartado 8, del Reglamento MDR.
- Afirmación: Quienes vendan o reciban implantes de clase III deben guardar sus identificadores únicos conforme al artículo 27, apartado 8, del MDR.

## eu-dev-031 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 4 · chunk 30 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: numeric
- Motivo de la propuesta: Tres fechas por clase conservadas en la paráfrasis.
- Premisa: En el caso de los productos sanitarios para diagnóstico in vitro, la identificación única debe colocarse a más tardar: 1. Dispositivos de la clase D: 26 de mayo de 2023 2. Dispositivos de clase B y clase C: 26 de mayo de
- Afirmación: El marcado UDI es exigible desde 2023 para la clase D, desde 2025 para las clases B y C, y desde 2027 para la clase A de diagnóstico in vitro.

## eu-dev-032 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 2 · chunk 4 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: numeric
- Motivo de la propuesta: Número de clases distinto (tres frente a cuatro). Contradicción numérica.
- Premisa: Los productos sanitarios se clasifican en cuatro clases (I, IIa, IIb, III).
- Afirmación: Los productos sanitarios se clasifican en tres clases de riesgo.

## eu-dev-033 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 2 · chunk 7 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: negation
- Motivo de la propuesta: La premisa exime por lo general; la afirmación lo exige siempre. Negación y alcance en la afirmación.
- Premisa: Los productos sanitarios de la clase I y los productos sanitarios para diagnóstico in vitro de la clase A, que son los productos de menor riesgo, por lo general no requieren la intervención de un organismo notificado par
- Afirmación: Los productos de diagnóstico in vitro de clase A siempre requieren la intervención de un organismo notificado.

## eu-dev-034 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 3 · chunk 19 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: numeric
- Motivo de la propuesta: La fecha marca el inicio de la obligación, no su fin. Inversión temporal.
- Premisa: A partir del 10 de enero de 2025, los fabricantes deben facilitar información a los Estados miembros, así como a los distribuidores y a los profesionales sanitarios, en caso de interrupción del suministro de determinados
- Afirmación: La obligación de informar sobre interrupciones del suministro terminó el 10 de enero de 2025.

## eu-dev-035 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 4 · chunk 29 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: numeric
- Motivo de la propuesta: Productos en investigación no mencionados en la premisa; compatible pero no inferible. Se conservan las fechas de la premisa.
- Premisa: En el caso de los productos sanitarios, la identificación única del producto debe colocarse, a más tardar, en: 1. Dispositivos de clase III y dispositivos implantables: 31 de mayo de 2021 2. Dispositivos de clase IIa y c
- Afirmación: El calendario de marcado UDI se aplica también a los productos en investigación.

## eu-dev-036 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 4 · chunk 36 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: coreference
- Motivo de la propuesta: La premisa impone entrega obligatoria; condicionarla a la solicitud contradice esa obligación. Alcance contradictorio.
- Premisa: Los centros sanitarios y los profesionales sanitarios están obligados a proporcionar la tarjeta de implante al paciente de que se trate (artículo 18, apartado 2, del Reglamento sobre los productos sanitarios).
- Afirmación: Dicha tarjeta de implante solo se entrega al paciente si este la solicita expresamente.

## eu-dev-037 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 2 · chunk 5 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: numeric
- Motivo de la propuesta: La premisa ordena el riesgo de A (menor) a D (mayor); la afirmación invierte el orden. Relación contradictoria.
- Premisa: En virtud de los Reglamentos, los productos sanitarios para diagnóstico in vitro se clasifican ahora en cuatro categorías (A, B, C o D, con un nivel de riesgo que aumenta de A a D) y se evalúan con arreglo a un enfoque b
- Afirmación: En el diagnóstico in vitro, la categoría A es la de mayor riesgo y la D la de menor.

## eu-dev-038 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 2 · chunk 8 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: ninguno
- Motivo de la propuesta: Publicación de informe anual no mencionada; compatible pero no inferible.
- Premisa: Además de la evaluación realizada por los organismos notificados, determinados productos de alto riesgo están sujetos a un examen adicional de sus expedientes clínicos por parte de un panel de expertos independientes con
- Afirmación: El panel de expertos publica cada año un informe con el número de expedientes revisados.

## eu-dev-039 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 4 · chunk 32 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: coreference
- Motivo de la propuesta: «Esta base de datos» remite a EUDAMED; el servicio de alertas no se menciona. Compatible pero no inferible.
- Premisa: EUDAMED permite a todas las partes interesadas acceder a información básica sobre productos sanitarios y productos sanitarios para diagnóstico in vitro, como la identidad del producto, su certificado, el fabricante, el r
- Afirmación: Esta base de datos ofrece además un servicio de alertas por correo para pacientes.

## eu-dev-040 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 3 · chunk 17 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: negation
- Motivo de la propuesta: Obligación de archivo no mencionada; compatible pero no inferible.
- Premisa: Los productos a medida están exentos de varios requisitos específicos del MDR, como el marcado CE, los identificadores únicos de los dispositivos (UDI), el resumen de la seguridad y el rendimiento clínico.
- Afirmación: Los distribuidores de productos a medida deben conservar una copia del contrato de compraventa durante diez años.

## eu-dev-041 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 3 · chunk 20 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: numeric
- Motivo de la propuesta: Destinatarios adicionales no mencionados; compatible pero no inferible. Se conserva la cifra de 6 meses en la premisa.
- Premisa: Los fabricantes deberán facilitar esta información al menos 6 meses antes de la interrupción o discontinuación prevista, excepto en circunstancias excepcionales (artículo 10 bis del Reglamento sobre los productos sanitar
- Afirmación: Los fabricantes deben avisar también a las asociaciones de pacientes antes de interrumpir un suministro.

## eu-dev-042 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Ficha informativa sanitaria · document_id 9af3bbaf… · split dev · página 3 · chunk 26 · rights p.5 (Reutilización con atribución indicada en el PDF) · sha256 638a33f31f2a1006…
- Fenómenos: ninguno
- Motivo de la propuesta: Exención no mencionada; compatible pero no inferible.
- Premisa: Por «operador económico» se entiende un fabricante, un representante autorizado, un importador o un distribuidor (artículo 2, apartado 35, del MDR y artículo 2, apartado 28, del IVDR).
- Afirmación: Los importadores paralelos quedan exentos de la definición de operador económico.

## eu-dev-043 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 2 · chunk 1 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: numeric
- Motivo de la propuesta: Fecha 2022 y alcance (dentro y fuera de Europa) conservados.
- Premisa: Para contribuir a hacer de Internet un lugar más seguro, en 2022 la Unión Europea (UE) creó el Reglamento de Servicios Digitales (DSA). Este reglamento se aplica a las plataformas en línea (tanto de Europa como del resto
- Afirmación: El Reglamento de Servicios Digitales, creado por la UE en 2022, se aplica a cualquier plataforma en línea accesible desde la Unión Europea, venga de donde venga.

## eu-dev-044 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 3 · chunk 2 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: numeric
- Motivo de la propuesta: Umbral 45 millones y ejemplos conservados.
- Premisa: Las plataformas más grandes, aquellas que tienen más de 45 millones de usuarios en la UE, como TikTok, Instagram o Snapchat, también deberán identificar y evaluar otros posibles riesgos para los niños y adolescentes que 
- Afirmación: Las plataformas con más de 45 millones de usuarios en la UE, como TikTok, Instagram o Snapchat, deben detectar y evaluar riesgos adicionales para los menores.

## eu-dev-045 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 6 · chunk 12 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: numeric
- Motivo de la propuesta: Edades 13/14 y alcance geográfico conservados.
- Premisa: ¿Sabías que... debes tener al menos 13 años (en España, 14) para poder usar TikTok, Snapchat, Instagram, BeReal y Steam?
- Afirmación: La edad mínima para usar TikTok o Instagram es de 13 años, y de 14 en España.

## eu-dev-046 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 5 · chunk 10 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: negation
- Motivo de la propuesta: La exclusión expresada con negación se parafrasea en afirmativo con el mismo alcance.
- Premisa: Nota: el DSA no se aplica a servicios de mensajería como Messenger o Telegram.
- Afirmación: Messenger y Telegram quedan fuera del ámbito del DSA por ser servicios de mensajería.

## eu-dev-047 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 7 · chunk 14 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: ninguno
- Motivo de la propuesta: Superlativo y medios conservados; enumeración con «:» en la premisa.
- Premisa: 3.Verificación de edad Es el método de mayor precisión. Comprueba tu edad mediante: > documentos oficiales, como el pasaporte (o DNI en España) > identificaciones digitales confiables, como un documento gubernamental o l
- Afirmación: La verificación de edad es el método más preciso y se basa en documentos oficiales o identidades digitales fiables.

## eu-dev-048 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 5 · chunk 7 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: ninguno
- Motivo de la propuesta: Enumeración completa conservada; viñetas unidas con comas.
- Premisa: Las plataformas deben respetar los derechos de los menores y actuar en el interés superior del menor. Esto incluye: ‣ derecho a la protección; ‣ derecho a la no discriminación; ‣ derecho a la inclusión; ‣ derecho a la pr
- Afirmación: Entre los derechos que las plataformas deben respetar están la protección, la no discriminación, la inclusión, la privacidad, la información y educación, la libertad de expresión y la participación.

## eu-dev-049 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 2 · chunk 0 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: negation
- Motivo de la propuesta: La premisa enumera seis riesgos; la afirmación los niega todos. Viñetas unidas con «;».
- Premisa: Pero el mundo virtual también presenta riesgos importantes. Allí, niños y adolescentes pueden: ‣ ser víctimas de ciberacoso; ‣ ser contactados por desconocidos con malas intenciones; ‣ ver contenido perjudicial o inadecu
- Afirmación: En el mundo virtual los menores no corren ningún riesgo.

## eu-dev-050 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 2 · chunk 2 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: coreference
- Motivo de la propuesta: «este reglamento» remite al DSA; la premisa obliga a todas las plataformas y la afirmación solo a las europeas.
- Premisa: Todas las plataformas en línea deben acatar este reglamento y contribuir a la seguridad de los usuarios de la UE.
- Afirmación: Solo las plataformas europeas deben acatar el reglamento.

## eu-dev-051 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 13 · chunk 26 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: negation
- Motivo de la propuesta: La premisa desaconseja esa función; la afirmación la recomienda. Viñetas unidas con «;».
- Premisa: Para evitar el uso excesivo y los comportamientos adictivos, así como para simplificar la desconexión, las plataformas no deberían incluir características como: ‣ desplazamiento infinito: cuando la página llega abajo del
- Afirmación: Las plataformas deberían incluir el desplazamiento infinito para mejorar la experiencia de los menores.

## eu-dev-052 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 10-11 · chunk 18 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa exige desactivarla por defecto; la afirmación exige activarla. Alcance contradictorio sin negación literal.
- Premisa: La configuración por defecto debería incluir: ‣ Limitación de contacto: control sobre quien puede seguir o mandar mensajes a niños y adolescentes ‣ Desactivar por defecto las características más peligrosas, como, por eje
- Afirmación: La geolocalización debe estar activada por defecto en las cuentas de los menores.

## eu-dev-053 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 15 · chunk 33 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: negation
- Motivo de la propuesta: La premisa prohíbe esas tácticas; la afirmación las permite.
- Premisa: ‣ no incurrir en tácticas de presión como: > temporizadores, > mensajes de «comprar ahora»,
- Afirmación: Las plataformas pueden usar temporizadores y mensajes de «comprar ahora» para animar las compras de los menores.

## eu-dev-054 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 6 · chunk 11 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: ninguno
- Motivo de la propuesta: Informe trimestral no mencionado; compatible pero no inferible.
- Premisa: El objetivo es encontrar el equilibrio entre: ‣ permitir que los niños y adolescentes compartan contenidos, ideas y reflexiones; ‣darles la oportunidad de explorar, jugar y aprender en línea... ... ¡pero siempre en un en
- Afirmación: Las plataformas deben publicar un informe trimestral con el tiempo medio de juego por tramo de edad.

## eu-dev-055 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 17 · chunk 37 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: coreference
- Motivo de la propuesta: «Este sistema» remite a la premisa; el gestor externo no se menciona. Compatible pero no inferible.
- Premisa: Las plataformas deben: ‣ contar con un sistema sencillo y claro para que cualquier usuario pueda denunciar abusos, acoso o contenido nocivo (incluidas las personas con discapacidad); ‣ permitir a los usuarios bloquear, s
- Afirmación: Este sistema de denuncias lo gestiona una empresa externa contratada por cada plataforma.

## eu-dev-056 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 9 · chunk 16 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: numeric
- Motivo de la propuesta: Canal de descarga no mencionado; compatible pero no inferible.
- Premisa: En julio de 2025 lanzó el proyecto para una aplicación de verificación de edad. Está diseñada para: ‣ que sea fácil de usar; ‣ que permita a los usuarios demostrar que tienen más de 18 años; ‣ evitar tener que proporcion
- Afirmación: La aplicación de verificación de edad se descarga gratuitamente desde las tiendas oficiales de aplicaciones.

## eu-dev-057 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 19 · chunk 40 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: ninguno
- Motivo de la propuesta: Lista anual de sanciones no mencionada; compatible pero no inferible.
- Premisa: Cada país de la UE cuenta con un Coordinador de Servicios Digitales (DSC) que trabaja con la Comisión Europea para controlar y supervisar de qué manera las plataformas aplican el DSA.
- Afirmación: El Coordinador de cada país publica una lista anual de plataformas sancionadas.

## eu-dev-058 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: El Reglamento de Servicios Digitales explicado · document_id 33740183… · split dev · página 12 · chunk 24 · rights p.24 (CC BY 4.0) · sha256 a46b03f851a76355…
- Fenómenos: negation
- Motivo de la propuesta: Plazo de 30 días no mencionado; compatible pero no inferible.
- Premisa: Pero si quieren personalizar su experiencia, deben ser capaces de hacerlo de una forma segura y adecuada a su edad. Para hacerlo correctamente, las plataformas deben: ‣ permitir que los usuarios menores ajusten la config
- Afirmación: Los cambios temporales de configuración caducan automáticamente al cabo de 30 días.

## eu-dev-059 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 4 · chunk 11 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: ninguno
- Motivo de la propuesta: Definición y enumeración de sectores conservadas.
- Premisa: Global Gateway es la estrategia de la Unión Europea (UE) para crear vínculos más sólidos y sostenibles entre Europa y el resto del mundo. Se centra en cinco sectores: digital, clima y energía, transporte, salud, educació
- Afirmación: La estrategia Global Gateway busca lazos más sólidos y sostenibles con el resto del mundo en cinco sectores: digital, clima y energía, transporte, salud, educación e investigación.

## eu-dev-060 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 4 · chunk 12 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: numeric
- Motivo de la propuesta: Año 2021 y cifra 300 000 millones conservados.
- Premisa: El plan se puso en marcha en 2021 y ayudará a movilizar hasta 300.000 millones de euros en inversiones, al reunir a la UE, sus Estados miembros y sus socios financieros y de desarrollo para que trabajen de forma coordina
- Afirmación: Global Gateway, lanzado en 2021, aspira a movilizar hasta 300 000 millones de euros en inversiones coordinadas.

## eu-dev-061 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 4 · chunk 14 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: ninguno
- Motivo de la propuesta: Enumeración de seis principios conservada; viñetas unidas con comas.
- Premisa: La estrategia Global Gateway se rige por seis principios clave para garantizar inversiones sostenibles y de alta calidad: • valores democráticos y altos estándares, • buena gobernanza y transparencia, • asociaciones equi
- Afirmación: Seis principios rigen Global Gateway: valores democráticos, gobernanza y transparencia, equidad en las alianzas, sostenibilidad, seguridad e impulso a la inversión privada.

## eu-dev-062 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 7 · chunk 22 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: numeric
- Motivo de la propuesta: Tres cifras y fecha 2028 conservadas.
- Premisa: El proyecto tiene como objetivo construir y equipar un hospital regional de atención terciaria con una capacidad de 340 camas de hospital y 78 camas en los servicios ambulatorios, en una superficie construida de 38.000 m
- Afirmación: El hospital de Bălți tendrá 340 camas de hospitalización y 78 ambulatorias en 38 000 m2 y estará terminado en 2028.

## eu-dev-063 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 10 · chunk 27 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: numeric
- Motivo de la propuesta: Longitud, países y factor 200 conservados.
- Premisa: El proyecto Medusa prevé la instalación de 7100 km de cable submarino de fibra óptica en el mar Mediterráneo. Este cable conectará los países del norte de África con España, Francia, Italia, Chipre y Portugal, con el obj
- Afirmación: El cable Medusa, de 7 100 km por el Mediterráneo, conectará el norte de África con cinco países europeos y multiplicará por 200 la velocidad en sus universidades.

## eu-dev-064 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 4 · chunk 11 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: numeric
- Motivo de la propuesta: Sectores distintos en número y contenido. Contradicción de alcance sin negación literal.
- Premisa: Se centra en cinco sectores: digital, clima y energía, transporte, salud, educación e investigación.
- Afirmación: Global Gateway se centra en tres sectores: defensa, pesca y turismo.

## eu-dev-065 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 17 · chunk 42 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: numeric
- Motivo de la propuesta: Periodo distinto con la misma cifra. Contradicción de fechas.
- Premisa: La estrategia Global Gateway tiene como objetivo movilizar hasta 300.000 millones de euros entre 2021 y 2027.
- Afirmación: El objetivo es movilizar hasta 300 000 millones de euros entre 2028 y 2034.

## eu-dev-066 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 6 · chunk 20 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: numeric
- Motivo de la propuesta: Cifra distinta (50 frente a 500). Contradicción numérica.
- Premisa: Gracias a la iniciativa WiFi4WB, la UE ofrece wifi público gratuito a 500 municipios de la región, lo que proporciona a los jóvenes, los estudiantes, las personas en busca de empleo y los propietarios de pequeñas empresa
- Afirmación: La iniciativa WiFi4WB ofrece wifi gratuito a 50 municipios de la región.

## eu-dev-067 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 7 · chunk 23 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: numeric
- Motivo de la propuesta: La premisa dice segundo; la afirmación dice primero. Relación de orden contradictoria.
- Premisa: Este proyecto tiene como objetivo construir una planta de desalinización en el golfo de Áqaba, en el mar Rojo, que distribuirá 300 millones de m3 de agua desalinizada al año por toda Jordania, el segundo país más afectad
- Afirmación: Jordania es el país más afectado por la escasez de agua del mundo.

## eu-dev-068 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 10 · chunk 28 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: ninguno
- Motivo de la propuesta: Ordinal distinto (segunda frente a primera). Contradicción sin negación literal.
- Premisa: La planta de HyIron Green Technologies es la primera fábrica de hierro con cero emisiones de África.
- Afirmación: La planta de HyIron es la segunda fábrica de hierro con cero emisiones de África.

## eu-dev-069 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 11 · chunk 30 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: ninguno
- Motivo de la propuesta: Conectividad ferroviaria y portuaria, energía verde e infraestructura digital conservadas. Se evita el pasaje con el artefacto de extracción «Medio￾Europa»; ver limitaciones.
- Premisa: Permitirá conectar las redes ferroviarias y los puertos para lograr un transporte de mercancías más rápido y eficiente, facilitará la producción y el transporte de energía verde, y mejorará la infraestructura digital
- Afirmación: El corredor IMEC incluye un tramo marítimo directo entre Bombay y El Pireo.

## eu-dev-070 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 6 · chunk 21 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: ninguno
- Motivo de la propuesta: Centrales nucleares no mencionadas; compatible pero no inferible.
- Premisa: Este proyecto también ayudará a Serbia a posicionarse como un centro neurálgico de la energía en el sudeste de Europa.
- Afirmación: Serbia construirá dos nuevas centrales nucleares para ese centro energético.

## eu-dev-071 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 8 · chunk 24 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: numeric
- Motivo de la propuesta: Tipo de contrato no mencionado; compatible pero no inferible.
- Premisa: El objetivo de este proyecto es fomentar la resiliencia, la identidad cultural y la cohesión social mediante la creación de oportunidades laborales y el desarrollo de las competencias de los jóvenes. Se trata de restaura
- Afirmación: Estos 5 000 puestos de trabajo son en su mayoría contratos indefinidos a tiempo completo.

## eu-dev-072 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 12 · chunk 32 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: numeric
- Motivo de la propuesta: Destino de exportación no mencionado; compatible pero no inferible.
- Premisa: La presa de Rogun se convertirá en el pilar principal de la red eléctrica de Tayikistán, ya que está previsto que duplique la producción energética del país y amplíe el acceso a una electricidad asequible y limpia para 1
- Afirmación: La presa de Rogun exportará la mitad de su producción a China.

## eu-dev-073 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 14 · chunk 36 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: ninguno
- Motivo de la propuesta: Plantilla no mencionada; compatible pero no inferible.
- Premisa: En el marco del programa de observación de la Tierra Copernicus de la UE en Filipinas, un nuevo centro de datos facilita el acceso y uso a los datos satelitales, lo que ayuda al país a gestionar las catástrofes y a lucha
- Afirmación: El nuevo centro de datos filipino emplea a más de doscientos ingenieros.

## eu-dev-074 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La estrategia Global Gateway · document_id a0d2cd8c… · split dev · página 16 · chunk 40 · rights p.2 (CC BY 4.0) · sha256 4fe9557df7c8a3ac…
- Fenómenos: ninguno
- Motivo de la propuesta: Becas no mencionadas; compatible pero no inferible.
- Premisa: Entre las iniciativas clave se encuentran el programa BELLA y el programa de observación de la Tierra Copernicus.
- Afirmación: El programa BELLA financia también becas de posgrado en inteligencia artificial.

## eu-dev-075 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 5 · chunk 9 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: ninguno
- Motivo de la propuesta: Alcance temporal (exclusivamente mientras dure) conservado.
- Premisa: El logotipo de la etiqueta ecológica de la UE puede utilizarse en productos y servicios, así como en el material promocional correspondiente, exclusivamente mientras dure el período de validez de la licencia concedida pa
- Afirmación: Solo durante la vigencia de la licencia puede usarse el logotipo, tanto en productos y servicios como en su material promocional.

## eu-dev-076 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 6 · chunk 9 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: negation
- Motivo de la propuesta: Triple negación de la premisa parafraseada en afirmativo con el mismo alcance.
- Premisa: Estilo: → No se modificará el estilo del logotipo. → No está permitido que otras imágenes o logotipos formen parte del logotipo de la etiqueta ecológica de la UE. → Está prohibido superponer texto al logotipo de la etiqu
- Afirmación: El estilo del logotipo es intocable: no admite otras imágenes ni texto superpuesto.

## eu-dev-077 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 6 · chunk 10 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: negation,numeric
- Motivo de la propuesta: Medida mínima conservada; negación convertida en mínimo afirmativo.
- Premisa: Tamaño: → El logotipo debe ser visible y legible. → El tamaño del logotipo no debe ser inferior a 10,6 x 10,6 mm
- Afirmación: El logotipo debe medir como mínimo 10,6 por 10,6 milímetros y ser visible y legible.

## eu-dev-078 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 10 · chunk 18 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: numeric
- Motivo de la propuesta: Estructura tripartita del código conservada.
- Premisa: XXXX Código de país: indica el Estado miembro en el que el titular de la licencia ha registrado un producto o servicio. YYY Código del grupo de productos/servicios: el código del grupo de productos que figura en la Decis
- Afirmación: El número de licencia combina el código del país de registro, el del grupo de productos y el de la solicitud asignado por el organismo competente.

## eu-dev-079 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 10 · chunk 19 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: numeric
- Motivo de la propuesta: Códigos 16/016 y regla de tres dígitos conservados.
- Premisa: El «0» se añade al código del grupo del producto textil para que el código conste de tres dígitos, a pesar de que en la Decisión de la Comisión dicho código es «16».
- Afirmación: El grupo textil figura como 16 en la Decisión, pero en la licencia aparece como 016 para completar tres dígitos.

## eu-dev-080 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 6 · chunk 11 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: negation
- Motivo de la propuesta: La premisa lo prohíbe; la afirmación lo permite. Alcance contradictorio.
- Premisa: Está prohibido asociar el logotipo a productos o servicios que no hayan obtenido la etiqueta ecológica de la UE o usarlo como parte del perfil general de una empresa titular de una licencia.
- Afirmación: El logotipo puede asociarse libremente a productos sin etiqueta ecológica.

## eu-dev-081 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 6 · chunk 12 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: numeric
- Motivo de la propuesta: La premisa permite una sola mención; la afirmación exige repetirla.
- Premisa: Si un titular de licencia tiene más de un producto registrado con una licencia, basta con indicar una sola vez el número de licencia junto al logotipo en cualquier material promocional relacionado.
- Afirmación: Con varios productos bajo una misma licencia hay que repetir el número junto a cada logotipo.

## eu-dev-082 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 16 · chunk 46 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa exige contactar; la afirmación lo exime.
- Premisa: Los interesados en utilizar la etiqueta ecológica de la UE para fines educativos distintos de los promocionales, deberán contactar con el servicio de asistencia de la etiqueta ecológica de la UE o con su organismo nacion
- Afirmación: El material educativo puede usar el logotipo sin contactar con nadie.

## eu-dev-083 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 17 · chunk 48 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: negation
- Motivo de la propuesta: La premisa lo prohíbe expresamente para ese caso.
- Premisa: El logotipo de la etiqueta ecológica de la UE puede mostrarse en productos impresos únicamente si se ha concedido la etiqueta a dichos productos de acuerdo con la Decisión (UE) 2020/1803 de la Comisión. No está permitido
- Afirmación: Si solo el papel tiene la etiqueta, puede mostrarse igualmente el logotipo del papel impreso.

## eu-dev-084 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 18 · chunk 55 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: negation
- Motivo de la propuesta: Prohibición directa invertida en la afirmación.
- Premisa: No está permitido colocar una pegatina con el logotipo de la etiqueta ecológica de la UE en dispensadores de jabón permanentes para comunicar que el jabón ha obtenido dicha etiqueta.
- Afirmación: Se permite colocar pegatinas del logotipo en dispensadores de jabón permanentes.

## eu-dev-085 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 10 · chunk 20 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa exige el número junto al logotipo; la afirmación lo declara omisible. Pasaje repetido en las páginas 10 y 11; se cita la primera aparición.
- Premisa: Cuando se muestre el logotipo de la etiqueta ecológica de la UE ( 2), debe aparecer el número de licencia correspondiente (preferiblemente cerca del logotipo).
- Afirmación: El número de licencia puede omitirse cuando se muestra el logotipo.

## eu-dev-086 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 4 · chunk 5 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: ninguno
- Motivo de la propuesta: Plazo de respuesta no mencionado; compatible pero no inferible.
- Premisa: En cualquiera de los dos casos, no olvide aportar la siguiente información: → datos de la persona interesada (si es titular de una licencia, indique siempre el/los número/s de la licencia en cuestión), → una justificació
- Afirmación: El servicio de asistencia responde a las solicitudes en un plazo máximo de cinco días laborables.

## eu-dev-087 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 14 · chunk 38 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: numeric
- Motivo de la propuesta: Placas de metal no mencionadas; compatible pero no inferible.
- Premisa: Las especificaciones para las placas de la etiqueta ecológica de la UE son: → Placa de vidrio: 20 cm x 20 cm → Imagen sobre el vidrio: 14,5 cm x 14,5 cm → Grosor: 0,8 cm → Tamaño de los tornillos: S8 → Distancia desde el
- Afirmación: Las placas de metal siguen las mismas dimensiones que las placas de vidrio.

## eu-dev-088 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 16 · chunk 44 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: ninguno
- Motivo de la propuesta: Reseñas no mencionadas; compatible pero no inferible.
- Premisa: En el ECAT público (catálogo de la etiqueta ecológica de la UE) figuran todos los productos y servicios a los que actualmente se ha concedido la etiqueta.
- Afirmación: El ECAT incluye también reseñas de consumidores sobre cada producto.

## eu-dev-089 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 15 · chunk 41 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: ninguno
- Motivo de la propuesta: Número de lenguas no mencionado; compatible pero no inferible.
- Premisa: «La etiqueta ecológica de la UE es la etiqueta oficial de excelencia medioambiental de la Unión Europea. Los productos con etiqueta ecológica de la UE tienen un impacto ambiental reducido a lo largo de múltiples etapas d
- Afirmación: Ese texto oficial debe imprimirse en al menos tres lenguas en cada envase.

## eu-dev-090 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La etiqueta ecológica de la UE · document_id aaf2a1b7… · split dev · página 10 · chunk 19 · rights p.2 (CC BY 4.0) · sha256 0fe7291fc19b5895…
- Fenómenos: numeric
- Motivo de la propuesta: Productos congelados no mencionados; compatible pero no inferible.
- Premisa: Para reproducir correctamente el número de licencia de la etiqueta ecológica de la UE, debe aplicarse el siguiente formato: → Tipo de letra: Verdana → Tamaño de fuente: 7 como mínimo (4,5 en el caso de productos impresos
- Afirmación: En los envases de productos congelados se exige un tamaño de fuente de 9 para el número de licencia.

## eu-dev-091 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 4 · chunk 3 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Cifra 27 y alcance (dentro y fuera) conservados en la paráfrasis.
- Premisa: La Unión Europea (UE) es una unión económica y política única entre veintisiete países europeos, que trabajan juntos para mejorar la vida de las personas en Europa e, incluso, fuera de ella.
- Afirmación: La UE es una unión económica y política singular de 27 países que cooperan para mejorar la vida dentro y fuera de Europa.

## eu-dev-092 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 4 · chunk 3 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: numeric
- Motivo de la propuesta: Tres cifras conservadas (6, 27, 450 millones). Edición 2025: «alrededor de 450».
- Premisa: A partir de seis países fundadores (o Estados miembros) en la década de 1950, ha ido creciendo hasta convertirse en una unión de veintisiete países con una población de alrededor de 450 millones de habitantes.
- Afirmación: Desde los seis fundadores de los años cincuenta, la UE ha crecido hasta 27 países y unos 450 millones de habitantes.

## eu-dev-093 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 6 · chunk 5 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: ninguno
- Motivo de la propuesta: Enumeración de valores conservada íntegramente.
- Premisa: Se trata del respeto de la dignidad humana, la libertad, la democracia, la igualdad, el Estado de Derecho y los derechos humanos.
- Afirmación: La UE se fundamenta en la dignidad humana, la libertad, la democracia, la igualdad, el Estado de Derecho y los derechos humanos.

## eu-dev-094 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 6 · chunk 7 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: ninguno
- Motivo de la propuesta: Periodicidad anual y destinatarios conservados.
- Premisa: Todos los años, el Parlamento Europeo otorga el Premio Sájarov a una persona u organización que lucha por los derechos humanos y las libertades fundamentales.
- Afirmación: El Parlamento Europeo concede cada año el Premio Sájarov a defensores de los derechos humanos y las libertades fundamentales.

## eu-dev-095 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 11 · chunk 11 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: negation,numeric,coreference
- Motivo de la propuesta: Cifra 800 000 millones y doble efecto conservados.
- Premisa: Con una inversión superior a los 800 000 millones de euros, NextGenerationEU no solo ha permitido a la UE responder a los retos de la pandemia de COVID-19, sino que también está ayudando a los países de la UE a revitaliz
- Afirmación: NextGenerationEU supera los 800 000 millones de euros y ha servido para responder a la pandemia y revitalizar las economías.

## eu-dev-096 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 12 · chunk 15 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: ninguno
- Motivo de la propuesta: Medida excepcional y cuatro ámbitos de acceso conservados.
- Premisa: También adoptó la medida excepcional de conceder protección temporal a millones de personas que huyen de Ucrania, proporcionándoles acceso a alojamiento, escuelas, asistencia sanitaria y empleo en la UE.
- Afirmación: La UE concedió protección temporal a millones de ucranianos con acceso a vivienda, escuelas, sanidad y empleo.

## eu-dev-097 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 6 · chunk 6 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: numeric
- Motivo de la propuesta: La premisa otorga la ciudadanía por nacionalidad de un Estado miembro, sin exigir residencia en él. Alcance contradictorio.
- Premisa: Si eres ciudadano de uno de los veintisiete países que integran la UE, también eres ciudadano de la UE.
- Afirmación: La ciudadanía de la UE solo corresponde a quienes residen en su país de origen.

## eu-dev-098 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 8 · chunk 9 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: negation,numeric
- Motivo de la propuesta: La premisa incluye cuatro países no UE; la afirmación los excluye. «únicamente» contradice la composición.
- Premisa: Veinticinco Estados miembros de la UE y cuatro países no pertenecientes a la UE (Islandia, Liechtenstein, Noruega y Suiza) pertenecen a lo que se conoce como espacio Schengen.
- Afirmación: El espacio Schengen lo forman únicamente Estados miembros de la UE.

## eu-dev-099 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 11 · chunk 11 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: ninguno
- Motivo de la propuesta: Finalidad distinta (defensa frente a recuperación pospandemia).
- Premisa: Para garantizar una rápida recuperación de la economía tras la pandemia, la UE creó un fondo de recuperación especial conocido como NextGenerationEU.
- Afirmación: NextGenerationEU se creó para financiar la ampliación del presupuesto de defensa.

## eu-dev-100 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 12 · chunk 15 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: coreference
- Motivo de la propuesta: La premisa incluye asistencia médica; la afirmación la excluye.
- Premisa: En el marco de su ayuda humanitaria, la UE ha proporcionado alimentos, refugio y asistencia médica a las personas afectadas por el conflicto.
- Afirmación: La ayuda humanitaria de la UE a Ucrania excluye la asistencia médica.

## eu-dev-101 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 14 · chunk 19 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Año distinto (2040 frente a 2030) con el mismo porcentaje. Contradicción de fecha.
- Premisa: Como primer hito de este ambicioso proyecto, la UE se ha comprometido a reducir sus emisiones netas de gases de efecto invernadero en al menos un 55 % de aquí a 2030, en comparación con los niveles de 1990.
- Afirmación: La UE se comprometió a reducir sus emisiones netas en al menos un 55 % de aquí a 2040.

## eu-dev-102 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 4 · chunk 3 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: coreference
- Motivo de la propuesta: Jornada conmemorativa no mencionada; compatible pero no inferible.
- Premisa: La UE lleva más de sesenta años trabajando por la paz, la prosperidad y el bienestar de sus ciudadanos.
- Afirmación: La UE celebra cada año una jornada conmemorativa de sus sesenta años de paz.

## eu-dev-103 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 6 · chunk 6 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: ninguno
- Motivo de la propuesta: Elecciones nacionales no mencionadas; compatible pero no inferible.
- Premisa: Esto te confiere otros derechos importantes, como la libertad de circular, vivir, trabajar y estudiar en cualquier país de la UE y el derecho de sufragio activo y pasivo en las elecciones locales y europeas, aunque vivas
- Afirmación: Muchos Estados permiten además votar en sus elecciones nacionales a residentes de otros países de la UE.

## eu-dev-104 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 6 · chunk 7 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: coreference
- Motivo de la propuesta: Importe y misiones concretas no mencionados; compatible pero no inferible.
- Premisa: Además de proteger los derechos de sus ciudadanos y de las personas que viven en la Unión Europea, la UE promueve los derechos humanos y unas elecciones justas en todo el mundo.
- Afirmación: La UE financia misiones internacionales de observación electoral con más de 50 millones anuales.

## eu-dev-105 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 8 · chunk 9 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: negation,coreference
- Motivo de la propuesta: Documento alternativo no mencionado; compatible pero no inferible.
- Premisa: Esto significa que no tienes que mostrar tu pasaporte al cruzar las fronteras entre estos países.
- Afirmación: En algunos pasos fronterizos se acepta también el documento de identidad en lugar del pasaporte.

## eu-dev-106 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE · document_id 736395fe… · split dev · página 12 · chunk 16 · rights p.2 (CC BY 4.0) · sha256 784f856adce4c096…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: El BEI como canal concreto no se menciona; compatible pero no inferible.
- Premisa: La UE, junto con sus Estados miembros y sus instituciones financieras, ha movilizado cerca de 120 000 millones de euros en apoyo global a Ucrania.
- Afirmación: Una parte de esos fondos se canaliza a través del Banco Europeo de Inversiones.

## eu-dev-107 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 11 · chunk 12 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: ninguno
- Motivo de la propuesta: Tres fuentes conservadas en la paráfrasis.
- Premisa: El dinero que gasta la UE (el presupuesto de la UE) proviene de varias fuentes: los derechos de aduana, las contribuciones basadas en el impuesto sobre el valor añadido (IVA) que recaudan los países de la UE y las contri
- Afirmación: El presupuesto de la UE se nutre de aranceles, de aportaciones ligadas al IVA y de contribuciones directas de los Estados.

## eu-dev-108 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 11 · chunk 13 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: negation,numeric
- Motivo de la propuesta: Fecha y hecho imponible conservados.
- Premisa: En enero de 2021 se introdujo una nueva fuente de ingresos: un impuesto sobre los residuos de envases de plástico no reciclados.
- Afirmación: Desde enero de 2021 existe un impuesto europeo sobre los residuos de envases plásticos no reciclados.

## eu-dev-109 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 14 · chunk 19 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: coreference
- Motivo de la propuesta: Enumeración de sectores conservada.
- Premisa: Todos los sectores de la sociedad y la economía deberán aportar su grano de arena, desde la industria, la energía y el transporte hasta la producción de alimentos, la agricultura y la construcción.
- Afirmación: La industria, la energía, el transporte, la alimentación, la agricultura y la construcción deben contribuir al esfuerzo climático.

## eu-dev-110 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 14 · chunk 20 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Porcentaje y periodo conservados.
- Premisa: Al menos el 30 % del gasto de la UE entre 2021 y 2027 se destinará a la lucha contra el cambio climático y sus efectos.
- Afirmación: Como mínimo el 30 % del gasto europeo de 2021 a 2027 combatirá el cambio climático.

## eu-dev-111 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 16 · chunk 24 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: ninguno
- Motivo de la propuesta: Cuatro ámbitos de inversión conservados.
- Premisa: Para que todos se pongan al día rápidamente y afianzar la posición de Europa como líder mundial en tecnología, la UE invierte en el desarrollo de las capacidades digitales, la supercomputación, la conectividad de alta ve
- Afirmación: La UE invierte en capacidades digitales, supercomputación, conectividad rápida y ciberseguridad para liderar la tecnología mundial.

## eu-dev-112 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 8 · chunk 9 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: La premisa incluye personas, servicios y dinero; «solo mercancías» contradice el alcance.
- Premisa: Gracias al mercado único, las personas, las mercancías, los servicios y el dinero pueden circular por los veintisiete países de la Unión casi tan libremente como dentro de un mismo país.
- Afirmación: El mercado único solo permite la circulación de mercancías entre los Estados miembros.

## eu-dev-113 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 12 · chunk 16 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: negation,coreference
- Motivo de la propuesta: La premisa afirma sanciones severas; la afirmación las niega.
- Premisa: La UE también ha encabezado la condena internacional de la guerra de agresión de Rusia contra Ucrania, y ha impuesto severas sanciones contra Rusia y sus cómplices en la guerra.
- Afirmación: La UE no ha impuesto ninguna sanción a Rusia por la guerra contra Ucrania.

## eu-dev-114 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 14 · chunk 20 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: numeric
- Motivo de la propuesta: Año distinto (2035 frente a 2040). Contradicción de fecha.
- Premisa: Para que la UE mantenga el objetivo de la neutralidad climática, el próximo paso será que todos los países de la UE lleguen a un acuerdo sobre un objetivo para 2040.
- Afirmación: El próximo paso es que todos los países acuerden un objetivo para 2035.

## eu-dev-115 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 14 · chunk 21 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: numeric
- Motivo de la propuesta: Cifra distinta (2 000 frente a 3 000 millones).
- Premisa: Bosques europeos protegidos y recuperados; 3 000 millones de árboles adicionales plantados de aquí a 2030.
- Afirmación: Se plantarán 2 000 millones de árboles adicionales de aquí a 2030.

## eu-dev-116 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 8 · chunk 9 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa permite el restablecimiento excepcional; la afirmación lo excluye siempre.
- Premisa: Los controles fronterizos en el interior del espacio Schengen pueden restablecerse excepcionalmente durante un tiempo limitado si existe una amenaza grave para la seguridad pública.
- Afirmación: Los controles fronterizos interiores de Schengen no pueden restablecerse en ningún caso.

## eu-dev-117 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 6 · chunk 6 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: numeric
- Motivo de la propuesta: Informe anual no mencionado; compatible pero no inferible. Premisa completa con la frase contigua que concreta las 24 lenguas.
- Premisa: También tienes derecho a presentar una petición al Parlamento Europeo, a recurrir al Defensor del Pueblo Europeo y a dirigirte por escrito a cualquier institución de la UE en una de las veinticuatro lenguas oficiales de 
- Afirmación: El Defensor del Pueblo publica un informe anual con el número de quejas por país.

## eu-dev-118 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 11 · chunk 12 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: coreference
- Motivo de la propuesta: Fecha de conclusión no mencionada; compatible pero no inferible.
- Premisa: Por ejemplo, en el contexto de la guerra de agresión de Rusia contra Ucrania y de la crisis energética mundial, ya está apoyando a los países de la UE en sus esfuerzos por eliminar gradualmente los combustibles fósiles r
- Afirmación: La eliminación de los combustibles fósiles rusos concluirá en 2027.

## eu-dev-119 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 12 · chunk 16 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: coreference
- Motivo de la propuesta: Medida concreta no mencionada; compatible pero no inferible.
- Premisa: Estas medidas tienen por objeto aislar económicamente a Rusia y limitar su capacidad de agresión militar.
- Afirmación: Las sanciones incluyen la congelación de activos de más de mil personas.

## eu-dev-120 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 14 · chunk 19 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: negation,numeric
- Motivo de la propuesta: Capacidad actual de absorción no mencionada; compatible pero no inferible.
- Premisa: Su objetivo es convertir a Europa en el primer continente climáticamente neutro de aquí a 2050, momento en el cual no produciremos más gases de efecto invernadero de los que nuestros ecosistemas puedan absorber de forma 
- Afirmación: Los ecosistemas europeos absorben actualmente unos 300 millones de toneladas de CO2 al año.

## eu-dev-121 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 14 · chunk 20 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: numeric
- Motivo de la propuesta: Cifra absoluta no mencionada; compatible pero no inferible.
- Premisa: Reducción en al menos un 55 % de las muertes por contaminación atmosférica de aquí a 2030.
- Afirmación: La contaminación atmosférica causa cada año más de 200 000 muertes prematuras en la UE.

## eu-dev-122 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Breve guía de la UE, edición 2024 · document_id 6e83d2c4… · split dev · página 16 · chunk 24 · rights p.2 (CC BY 4.0) · sha256 c259c961bd78e66f…
- Fenómenos: coreference
- Motivo de la propuesta: «este tipo» remite a los laboratorios de análisis; fábricas nuevas no mencionadas. Compatible pero no inferible.
- Premisa: Los laboratorios de este tipo son esenciales para que la UE pueda producir sus propios microchips y ser tecnológicamente independiente.
- Afirmación: La UE construirá tres nuevas fábricas de microchips antes de 2030.

## eu-dev-123 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 7 · chunk 11 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: ninguno
- Motivo de la propuesta: Paráfrasis fiel sin cifras ni negación.
- Premisa: La profesión docente sigue siendo una opción profesional atractiva en España, especialmente en el sector público.
- Afirmación: La docencia sigue siendo una salida profesional atractiva en España, sobre todo en la pública.

## eu-dev-124 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 7 · chunk 12 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: ninguno
- Motivo de la propuesta: Paráfrasis fiel de la comparación salarial.
- Premisa: Los salarios de los profesores son competitivos con respecto a otras profesiones que requieren cualificaciones educativas similares.
- Afirmación: El sueldo del profesorado compite con el de otras profesiones de cualificación similar.

## eu-dev-125 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 8 · chunk 14 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: ninguno
- Motivo de la propuesta: Motivo principal conservado en la paráfrasis.
- Premisa: Adquirir la condición de funcionario con un status de empleo permanente es una de las principales razones para elegir una carrera docente.
- Afirmación: Conseguir una plaza fija de funcionario es uno de los principales motivos para ser docente.

## eu-dev-126 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 8 · chunk 15 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: coreference
- Motivo de la propuesta: Contraste general/carencias STEM conservado.
- Premisa: España tiene suficientes profesores en general, pero tiene carencias en las materias de ciencia, tecnología, ingeniería y matemáticas (STEM por sus siglas en inglés).
- Afirmación: España dispone de docentes suficientes en general, pero le faltan en ciencias, tecnología, ingeniería y matemáticas.

## eu-dev-127 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 9 · chunk 20 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: numeric
- Motivo de la propuesta: Cuatro porcentajes conservados.
- Premisa: Las mujeres representan el 95 % de los profesores de atención y educación de la primera infancia; el 77 % en primaria, el 62 % en el primer ciclo de enseñanza secundaria y el 57 % en el segundo ciclo (MEFP, 2022).
- Afirmación: Las mujeres son el 95 % en infantil, el 77 % en primaria, el 62 % en el primer ciclo de secundaria y el 57 % en el segundo.

## eu-dev-128 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 7 · chunk 11 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa afirma exceso de estudiantes; la afirmación afirma defecto.
- Premisa: Cada año, el número de estudiantes universitarios matriculados en estudios de grado o máster es superior a la demanda real de puestos docentes.
- Afirmación: Cada año hay menos universitarios en educación que plazas docentes disponibles.

## eu-dev-129 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 8 · chunk 14 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: negation,numeric
- Motivo de la propuesta: La premisa afirma limitación hasta 2021; «nunca» la niega en todo tiempo.
- Premisa: Sin embargo, el acceso a la función pública como docente estuvo limitado hasta 2021 debido al escaso número de vacantes publicadas.
- Afirmación: El acceso a la función pública docente nunca ha estado limitado.

## eu-dev-130 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 8 · chunk 17 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: negation,numeric
- Motivo de la propuesta: La premisa deja más de 720 sin cubrir; la afirmación dice ninguna.
- Premisa: En las oposiciones generales de 2021 para profesores de enseñanza secundaria pública, quedaron sin cubrir más de 720 plazas de profesores de matemáticas (hasta el 50 % de todos los puestos vacantes en determinadas region
- Afirmación: En las oposiciones de 2021 se cubrieron todas las plazas de matemáticas.

## eu-dev-131 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 8 · chunk 18 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: numeric
- Motivo de la propuesta: La premisa sitúa a España por debajo (20,2 frente a 24,5); la afirmación la sitúa por encima. Relación contradictoria.
- Premisa: En 2021, la proporción de profesores (CINE 1-3) mayores de cincuenta y cinco años era por término medio del 20,2 %, por debajo de la media de la UE del 24,5 %4 .
- Afirmación: La proporción de docentes mayores de 55 años en España supera la media de la UE.

## eu-dev-132 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 9 · chunk 19 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: negation,coreference
- Motivo de la propuesta: Dirección de la tendencia invertida (aumenta frente a disminuye).
- Premisa: La mayoría de los profesores son mujeres; sin embargo, su participación en el cuerpo docente disminuye a medida que aumenta el nivel educativo.
- Afirmación: La presencia de mujeres aumenta a medida que sube el nivel educativo.

## eu-dev-133 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 9 · chunk 21 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: numeric
- Motivo de la propuesta: La premisa afirma más de cuarenta años invariable; la afirmación impone un ciclo decenal.
- Premisa: También se están preparando reformas en el acceso a la profesión docente, que ha permanecido invariable durante más de cuarenta años.
- Afirmación: El acceso a la profesión docente se reforma cada diez años.

## eu-dev-134 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 7 · chunk 12 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: numeric
- Motivo de la propuesta: La excepción de infantil no fija su posición; compatible pero no inferible.
- Premisa: La proporción de alumnos por profesor es inferior a la media de la UE (excepto en la educación infantil)2 y la carga de trabajo de los profesores es comparable.
- Afirmación: La ratio en educación infantil es la más baja de la UE.

## eu-dev-135 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 7 · chunk 13 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: negation,coreference
- Motivo de la propuesta: Portugal no se menciona; compatible pero no inferible.
- Premisa: Al igual que la mayoría de sus homólogos europeos, los profesores españoles no se sienten tan valorados por la sociedad como antaño.
- Afirmación: La falta de reconocimiento afecta también a los docentes portugueses.

## eu-dev-136 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 8 · chunk 15 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: ninguno
- Motivo de la propuesta: Tasa concreta no mencionada; compatible pero no inferible.
- Premisa: La elevada rotación del profesorado puede tener un impacto negativo en la satisfacción laboral, los resultados educativos y la eficacia de los proyectos pedagógicos.
- Afirmación: La rotación del profesorado supera el 15 % anual en las grandes ciudades.

## eu-dev-137 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 8 · chunk 18 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: numeric
- Motivo de la propuesta: Incentivos no mencionados; compatible pero no inferible.
- Premisa: La situación también difiere a escala autonómica, con intervalos de entre el 21 y el 48 % de profesores mayores de cincuenta años (MEFP, 2023a).
- Afirmación: Las comunidades con más docentes mayores ofrecen incentivos para jubilarse antes.

## eu-dev-138 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Monitor de la educación y la formación de 2023 · document_id bc11dbbe… · split dev · página 9 · chunk 21 · rights p.2 (CC BY 4.0) · sha256 8a34cee6a36447f0…
- Fenómenos: ninguno
- Motivo de la propuesta: Prueba nacional no mencionada; compatible pero no inferible.
- Premisa: España está adaptando las competencias del profesorado para satisfacer las necesidades educativas modernas, en particular las capacidades digitales y ecológicas.
- Afirmación: El nuevo marco de competencias digitales se evaluará con una prueba nacional en 2026.

## eu-dev-139 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 5 · chunk 10 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: numeric
- Motivo de la propuesta: Triple 20 % conservado en la paráfrasis.
- Premisa: Los objetivos para 2020 de reducción del 20 % en las emisiones de gases de efecto invernadero, el 20 % de energías renovables y el incremento en un 20 % de la eficiencia energética fueron pioneros en aquel momento.
- Afirmación: Los objetivos de 2020 combinaban un triple 20 %: emisiones, renovables y eficiencia energética.

## eu-dev-140 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 6 · chunk 11 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: numeric
- Motivo de la propuesta: Porcentaje y año conservados.
- Premisa: Con el Acuerdo de París, la UE se ha comprometido a seguir avanzando y lograr una reducción de las emisiones de gases de efecto invernadero de al menos un 40 % para 2030.
- Afirmación: En el marco del Acuerdo de París, la UE se comprometió a recortar sus emisiones al menos un 40 % para 2030.

## eu-dev-141 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 6 · chunk 13 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: «Dicho sector» son los edificios según la frase anterior del documento; cifras 40 % y 36 % conservadas.
- Premisa: Dicho sector es crucial para la transición hacia una energía limpia, dado que los edificios son los mayores consumidores de energía, ya que representan el 40 % del consumo final de energía y el 36 % de las emisiones de g
- Afirmación: Los edificios, mayores consumidores de energía, suponen el 40 % del consumo final y el 36 % de las emisiones en Europa.

## eu-dev-142 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 6 · chunk 14 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Porcentaje, año y carácter vinculante conservados.
- Premisa: Este nuevo y ambicioso objetivo de alcanzar al menos un 32 % en energías renovables para 2030, vinculante a escala de la UE, impulsará una aceleración de la utilización de energía limpia en todos los sectores y facilitar
- Afirmación: El objetivo de al menos un 32 % de renovables en 2030 es vinculante para toda la UE.

## eu-dev-143 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 11 · chunk 39 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: coreference
- Motivo de la propuesta: Proporción y composición conservadas.
- Premisa: La Unión Europea (UE) actualmente importa más de la mitad de su energía, principalmente en forma de petróleo y gas.
- Afirmación: Más de la mitad de la energía de la UE es importada, sobre todo petróleo y gas.

## eu-dev-144 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 17 · chunk 66 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: coreference
- Motivo de la propuesta: Mecanismo (sumar recursos, incentivos) conservado.
- Premisa: Los ciudadanos pueden unirse a «comunidades de energía» sumando sus recursos energéticos y beneficiarse de incentivos para la producción de energía renovable.
- Afirmación: Quienes se unan a una comunidad de energía pueden sumar recursos y recibir incentivos por producir renovables.

## eu-dev-145 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 6 · chunk 13 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: numeric
- Motivo de la propuesta: Porcentaje distinto (20 frente a 32). Viñetas unidas con «;».
- Premisa: Objetivos energéticos de la UE para 2030 ● Al menos un 40 % de reducción en las emisiones de gases de efecto invernadero ● Al menos un 32 % de energías renovables en el consumo de energía ● Al menos un 32,5 % en eficienc
- Afirmación: El objetivo de renovables para 2030 es del 20 % del consumo de energía.

## eu-dev-146 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 6 · chunk 17 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Conferencia y sede distintas (COP24 Katowice 2018 frente a COP25 Madrid).
- Premisa: Con la mirada puesta más allá de 2030, la Comisión Europea, en el contexto de las conversaciones sobre el clima de la COP24 en Katowice de diciembre de 2018, presentó su Estrategia de neutralidad climática a largo plazo 
- Afirmación: La Estrategia de neutralidad climática se presentó en la COP25 de Madrid.

## eu-dev-147 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 10 · chunk 38 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: numeric
- Motivo de la propuesta: Cifra distinta (siete frente a catorce regiones; siete son los Estados).
- Premisa: La UE ya está prestando asistencia a catorce regiones del carbón en siete Estados miembros.
- Afirmación: La UE presta asistencia a siete regiones del carbón.

## eu-dev-148 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 20 · chunk 81 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: numeric
- Motivo de la propuesta: Año distinto (2050 frente a 2070). Contradicción de fecha.
- Premisa: El mundo tendrá que alcanzar cero emisiones de gases de efecto invernadero alrededor de 2070 para limitar el aumento de temperatura a 1,5 grados Celsius.
- Afirmación: El mundo debe llegar a cero emisiones alrededor de 2050 para limitar el calentamiento a 1,5 grados.

## eu-dev-149 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 8 · chunk 28 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa exige la menor huella posible; la afirmación la ignora.
- Premisa: Almacenamiento de electricidad: Europa apoya el desarrollo de una cadena de valor doméstica que produzca baterías «verdes» basadas en celdas de batería de alto rendimiento, seguras y con la menor huella ambiental posible
- Afirmación: Europa apoya baterías domésticas de alto rendimiento sin importar su huella ambiental.

## eu-dev-150 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 6 · chunk 15 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: numeric
- Motivo de la propuesta: Horizonte distinto (diez frente a treinta años).
- Premisa: Los planes nacionales también requieren que los países de la UE definan una estrategia a largo plazo por lo menos durante los próximos treinta años.
- Afirmación: Los países de la UE deben definir una estrategia a diez años vista.

## eu-dev-151 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 16 · chunk 63 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: ninguno
- Motivo de la propuesta: Requisito técnico no mencionado; compatible pero no inferible.
- Premisa: Por ejemplo, los precios dinámicos en la electricidad ofrecen el mejor valor (es decir, los precios más bajos a lo largo del tiempo) para los consumidores.
- Afirmación: Los precios dinámicos exigen un contador inteligente de última generación.

## eu-dev-152 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 5 · chunk 9 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: numeric
- Motivo de la propuesta: Revisión periódica no mencionada; compatible pero no inferible.
- Premisa: Al establecer ambiciosos objetivos energéticos y climáticos para 2030, la UE da un claro ejemplo de la dirección de los esfuerzos.
- Afirmación: La UE revisa estos objetivos cada cinco años.

## eu-dev-153 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 21 · chunk 86 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Distribución geográfica no mencionada; compatible pero no inferible.
- Premisa: Es cierto que existen beneficios económicos de esta transición (nuevos empleos y hasta un aumento adicional del 2 % del producto interior bruto), pero también hay otras ventajas, en términos de mejor calidad del aire y s
- Afirmación: El aumento del PIB se concentra en los países del norte.

## eu-dev-154 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 15 · chunk 57 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: ninguno
- Motivo de la propuesta: Periodicidad no mencionada; compatible pero no inferible.
- Premisa: Creada para ayudar a consolidar el mercado interior de la energía en Europa, la ACRE emitirá en el futuro informes de mejores prácticas en una serie de áreas, lo que ayudará a alinear los enfoques de los diferentes Estad
- Afirmación: Los informes de la ACRE se publican cada dos años.

## eu-dev-155 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 16 · chunk 60 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: coreference
- Motivo de la propuesta: Ayudas directas concretas no mencionadas; compatible pero no inferible.
- Premisa: Además, esta democratización de la energía aliviará la pobreza energética y protegerá a los ciudadanos vulnerables.
- Afirmación: La democratización de la energía incluye ayudas directas para pagar la factura de la luz.

## eu-dev-156 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Energía limpia para todos los europeos · document_id b4e46873… · split dev · página 20 · chunk 79 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 83e77d3b7bc29d2f…
- Fenómenos: negation,numeric
- Motivo de la propuesta: Fecha de aprobación no mencionada; compatible pero no inferible.
- Premisa: Los objetivos de la Unión Europea (UE) para 2030 son importantes, pero la transición energética no se detendrá allí.
- Afirmación: La estrategia posterior a 2030 se aprobará en 2028.

## eu-dev-157 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 3 · chunk 3 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: coreference
- Motivo de la propuesta: Participación récord y mandato (valientes y decididos) conservados.
- Premisa: Los ciudadanos europeos hicieron oír su voz y sus aspiraciones con una participación récord en las elecciones al Parlamento Europeo de este año, y encomendaron a las instituciones y los dirigentes europeos la clara tarea
- Afirmación: Con una participación récord, los votantes pidieron a las instituciones europeas valentía y decisión.

## eu-dev-158 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 5 · chunk 10 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Carácter pionero y año 2050 conservados.
- Premisa: Este pacto incluirá el primer acto legislativo climático europeo que consagrará en una norma el objetivo de neutralidad climática para 2050.
- Afirmación: El pacto incluirá la primera ley climática europea con la neutralidad en 2050 como norma.

## eu-dev-159 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 5 · chunk 11 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: ninguno
- Motivo de la propuesta: Dos medidas conservadas en la paráfrasis.
- Premisa: Propondré la ampliación del régimen de comercio de derechos de emisión a fin de cubrir el sector marítimo y reducir los derechos gratuitos asignados a las compañías aéreas.
- Afirmación: El comercio de emisiones se extenderá al transporte marítimo y recortará los derechos gratuitos de las aerolíneas.

## eu-dev-160 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 8 · chunk 26 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: ninguno
- Motivo de la propuesta: Finalidad (financiación de pymes) y tres verbos conservados.
- Premisa: Concluiremos la Unión de los Mercados de Capitales para garantizar que las pymes tengan acceso a la financiación que necesitan para crecer, innovar y expandirse.
- Afirmación: Completar la Unión de Mercados de Capitales debe dar a las pymes financiación para crecer, innovar y expandirse.

## eu-dev-161 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 10 · chunk 33 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: numeric
- Motivo de la propuesta: Plazo de 100 días y alcance (todos los trabajadores) conservados.
- Premisa: En los 100 primeros días de mi mandato, propondré un instrumento jurídico para garantizar que todos los trabajadores de nuestra Unión tengan un salario mínimo justo.
- Afirmación: En sus cien primeros días propondrá una norma para un salario mínimo justo para todos los trabajadores.

## eu-dev-162 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 10 · chunk 36 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: coreference
- Motivo de la propuesta: Destinatarios y finalidad conservados.
- Premisa: Europa debe apoyar también a los padres y a las personas con responsabilidades asistenciales a equilibrar mejor su trabajo y su vida familiar.
- Afirmación: Padres y cuidadores deben recibir apoyo para conciliar trabajo y vida familiar.

## eu-dev-163 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 4 · chunk 4 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa exige liderar; la afirmación propone seguir. Relación contradictoria sin negación literal.
- Premisa: Europa debe liderar la transición hacia un planeta sano y un nuevo mundo digital.
- Afirmación: Europa debe seguir a otros continentes en la transición ecológica y digital.

## eu-dev-164 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 4 · chunk 6 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: negation
- Motivo de la propuesta: Máximo histórico frente a mínimo histórico.
- Premisa: Nuestro nivel de empleo es más alto que nunca y gozamos de un crecimiento económico sostenido.
- Afirmación: El nivel de empleo está en mínimos históricos.

## eu-dev-165 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 5 · chunk 11 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: numeric
- Motivo de la propuesta: Porcentaje distinto (60 frente a 40).
- Premisa: Actualmente, nuestro objetivo para 2030 es reducir un 40 % las emisiones, pero hemos de ser más ambiciosos.
- Afirmación: El objetivo actual para 2030 es reducir las emisiones un 60 %.

## eu-dev-166 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 5 · chunk 12 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: negation,coreference
- Motivo de la propuesta: La premisa anuncia el impuesto; la afirmación lo niega.
- Premisa: Para complementar esta labor y garantizar que nuestras empresas puedan competir en igualdad de condiciones, implantaré un impuesto sobre el carbono en frontera para evitar fugas de carbono.
- Afirmación: No se creará ningún impuesto sobre el carbono en frontera.

## eu-dev-167 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 11 · chunk 38 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: numeric
- Motivo de la propuesta: Porcentaje distinto (10 frente a 40).
- Premisa: El 40 % de nosotros se enfrentará al cáncer en algún momento de la vida, y casi todos conoceremos la ansiedad y el dolor de un amigo o familiar que lo padezca.
- Afirmación: El 10 % de la población se enfrentará al cáncer en algún momento de su vida.

## eu-dev-168 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 13 · chunk 48 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa abre la mayoría cualificada; la afirmación mantiene la unanimidad.
- Premisa: Haré uso de las cláusulas de los Tratados que permiten que las propuestas sobre fiscalidad se adopten mediante codecisión y se decidan por mayoría cualificada en el Consejo.
- Afirmación: Las propuestas fiscales deberán seguir decidiéndose por unanimidad en el Consejo.

## eu-dev-169 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 4 · chunk 6 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: ninguno
- Motivo de la propuesta: Oficinas en capitales no mencionadas; compatible pero no inferible.
- Premisa: Deseo reforzar la asociación de la Comisión con el Parlamento Europeo, la voz de los ciudadanos.
- Afirmación: La Comisión abrirá una oficina conjunta con el Parlamento en cada capital.

## eu-dev-170 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 6 · chunk 13 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: coreference
- Motivo de la propuesta: Fondo concreto no mencionado; compatible pero no inferible.
- Premisa: Por esta razón, creo que lo que es bueno para nuestro planeta debe ser bueno para nuestra población, nuestras regiones y nuestra economía.
- Afirmación: Las regiones mineras recibirán un fondo específico de 10 000 millones.

## eu-dev-171 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 6 · chunk 14 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: negation,coreference
- Motivo de la propuesta: Periodo concreto no mencionado; compatible pero no inferible.
- Premisa: En esta transición debemos reconocer y respetar que no todos empiezan desde el mismo punto.
- Afirmación: Los países con menor renta dispondrán de un periodo transitorio de cinco años.

## eu-dev-172 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 6 · chunk 17 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: coreference
- Motivo de la propuesta: Sede no mencionada; compatible pero no inferible.
- Premisa: Como parte de ello, también propondré transformar partes del Banco Europeo de Inversiones en el banco climático europeo.
- Afirmación: El banco climático europeo tendrá su sede en Fráncfort.

## eu-dev-173 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 9 · chunk 28 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: ninguno
- Motivo de la propuesta: Tasa concreta no mencionada; compatible pero no inferible.
- Premisa: Necesitamos un entorno de inversión más atractivo y un crecimiento que cree puestos de trabajo de calidad, especialmente para los jóvenes.
- Afirmación: El desempleo juvenil supera el 30 % en el sur de Europa.

## eu-dev-174 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Una Unión que se esfuerza por lograr más resultados · document_id 43a17056… · split dev · página 12 · chunk 45 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 b1890477003a65a6…
- Fenómenos: coreference
- Motivo de la propuesta: Tipo concreto no mencionado; compatible pero no inferible.
- Premisa: Una carrera de mínimos en materia tributaria socava la capacidad de los países para establecer políticas fiscales que satisfagan las necesidades de sus economías y sus ciudadanos.
- Afirmación: Varios Estados ya aplican un tipo mínimo común del 20 % para sociedades.

## eu-dev-175 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 6 · chunk 16 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: coreference
- Motivo de la propuesta: Destinatarios y finalidad conservados.
- Premisa: Las siguientes directrices han sido elaboradas para ayudar a los docentes y educadores, desde el personal docente y de apoyo hasta los equipos directivos de centros educativos, a tomar decisiones relativas al uso de cont
- Afirmación: Estas directrices ayudan a docentes, personal de apoyo y equipos directivos a decidir sobre el uso de CED.

## eu-dev-176 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 11 · chunk 36 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Tres modalidades conservadas; «3D» es la cifra del fenómeno.
- Premisa: Estas actividades de evaluación suelen presentarse en forma de juego. ● El alumnado puede crear sus propios porfolios digitales en los que reflexiona sobre sus experiencias de aprendizaje y documenta el desarrollo de un 
- Afirmación: La evaluación con CED puede usar juegos, porfolios digitales y realidad virtual con modelos 3D.

## eu-dev-177 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 15 · chunk 54 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Edición y número de áreas conservados.
- Premisa: DigComp (Marco Europeo de Competencia Digital para la Ciudadanía), ya en su quinta edición (DigComp 3.0), describe los conocimientos, habilidades y actitudes necesarios en cinco áreas de competencia (búsqueda, evaluación
- Afirmación: DigComp 3.0, en su quinta edición, define conocimientos, habilidades y actitudes en cinco áreas.

## eu-dev-178 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 24 · chunk 85 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: ninguno
- Motivo de la propuesta: Requisito de procedencia y de etiquetado conservados.
- Premisa: Asegúrate de que todos los contenidos proceden de editoriales y proveedores de tecnología educativa de confianza, instituciones acreditadas, repositorios de REA revisados por otros docentes o portales nacionales de recur
- Afirmación: Los contenidos deben venir de fuentes de confianza y el material generado por IA debe etiquetarse siempre.

## eu-dev-179 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 26 · chunk 93 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: coreference
- Motivo de la propuesta: Paráfrasis fiel de causa y doble efecto.
- Premisa: Dar prioridad a un CED que demuestre un impacto contrastado ayuda a los centros a mejorar su práctica docente y a aprovechar mejor sus recursos.
- Afirmación: Priorizar un CED con impacto demostrado mejora la práctica docente y el uso de recursos.

## eu-dev-180 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 36 · chunk 120 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: numeric
- Motivo de la propuesta: Secuencia (paso 1) y contenido conservados.
- Premisa: Paso 1: Buscar el contenido adecuado Define tus objetivos de aprendizaje y enseñanza y valora en qué y cómo los CED pueden apoyarlos mejor.
- Afirmación: El primer paso es definir objetivos de aprendizaje y valorar cómo los CED los apoyan.

## eu-dev-181 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 42 · chunk 141 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: coreference
- Motivo de la propuesta: Formatos y destinos conservados.
- Premisa: Estas herramientas ofrecen la posibilidad de crear CED como texto, imágenes (incluyendo fotografías, pinturas digitales y dibujos animados), vídeos y música, que luego pueden incorporarse a secuencias didácticas, activid
- Afirmación: Estas herramientas permiten crear texto, imágenes, vídeos y música para secuencias didácticas y cuestionarios.

## eu-dev-182 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 6 · chunk 12 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: negation
- Motivo de la propuesta: La premisa afirma inversiones en varios países; la afirmación las niega.
- Premisa: Para no quedarse atrás en el proceso de digitalización, los distintos países han invertido en equipamiento digital, conectividad e infraestructuras, así como en formación en competencia digital para el personal docente, 
- Afirmación: Ningún país ha invertido en equipamiento digital para sus docentes.

## eu-dev-183 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 9 · chunk 24 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: negation,coreference
- Motivo de la propuesta: La premisa permite el uso conjunto; la afirmación lo prohíbe.
- Premisa: Estos contenidos pueden ser utilizados junto con recursos educativos no digitales para apoyar las actividades de enseñanza, aprendizaje y evaluación del aula.
- Afirmación: Los CED no pueden combinarse con recursos no digitales.

## eu-dev-184 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 13 · chunk 47 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: coreference
- Motivo de la propuesta: La premisa lo permite; la afirmación lo prohíbe.
- Premisa: Los profesores pueden desarrollar su propio CED, más adaptado a las necesidades y contextos concretos de sus alumnos, en ocasiones utilizando una serie de herramientas, que incluye la IA.
- Afirmación: Los profesores tienen prohibido crear su propio CED.

## eu-dev-185 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 20 · chunk 73 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: negation,coreference
- Motivo de la propuesta: La premisa lo niega y exige pensar, hacer, discutir y reflexionar.
- Premisa: De la misma forma, los mejores recursos digitales no se limitan a presentar hechos. Exigen a los estudiantes que piensen, hagan, discutan y reflexionen.
- Afirmación: Los mejores recursos digitales se limitan a presentar hechos.

## eu-dev-186 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 28 · chunk 98 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa afirma agilizar y asegurar; la afirmación invierte el efecto.
- Premisa: Por ejemplo, el Gestionnaire d'Accès aux Ressources (GAR) francés ayuda a agilizar y asegurar el acceso a los CED tanto al alumnado como al profesorado.
- Afirmación: El GAR francés dificulta el acceso a los CED.

## eu-dev-187 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 39 · chunk 128 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: negation,coreference
- Motivo de la propuesta: La lista de comprobación incluye la integración; la afirmación la declara irrelevante. Ítems unidos con «.».
- Premisa: Si se integra sin problemas con la tecnología de que dispone el centro educativo ● Si requiere formación adicional para ella, el resto de docentes y el alumnado ● Si resulta sencillo obtener apoyo técnico o pedagógico po
- Afirmación: Al elegir un CED no importa si se integra con la tecnología del centro.

## eu-dev-188 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 44 · chunk 149 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: coreference
- Motivo de la propuesta: La premisa afirma la integración posible; la afirmación la niega.
- Premisa: Estos espacios suelen facilitar el acceso a materiales sometidos a curación, a través de una ubicación segura y pueden integrarse en el sistema de gestión del aprendizaje (LMS) de un centro educativo o en entornos virtua
- Afirmación: Estos espacios no pueden integrarse en el LMS del centro.

## eu-dev-189 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 12 · chunk 40 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: ninguno
- Motivo de la propuesta: Plan mensual no mencionado; compatible pero no inferible. Se conserva la redacción extraída.
- Premisa: El profesorado pueden utilizar los CED para proporcionar materiales de aprendizaje diferenciados para cada estudiante.
- Afirmación: Cada estudiante recibe un plan de aprendizaje individual revisado cada mes.

## eu-dev-190 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 18 · chunk 69 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: coreference
- Motivo de la propuesta: Revisión trimestral no mencionada; compatible pero no inferible.
- Premisa: También pueden establecerse hitos compartidos para el uso de los CED, haciendo que su adopción sea altamente estratégica.
- Afirmación: Los hitos compartidos se revisan en reuniones trimestrales.

## eu-dev-191 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 25 · chunk 90 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: ninguno
- Motivo de la propuesta: Registro anual no mencionado; compatible pero no inferible. Premisa en forma de preguntas de comprobación.
- Premisa: ¿Este contenido proviene de una fuente que conozco y en la que confío? ● ¿Los contenidos que utilizo son precisos, actuales y apropiados? ● ¿Funciona de forma fiable en la infraestructura informática de nuestro centro? ●
- Afirmación: Los centros deben documentar estas comprobaciones en un registro anual.

## eu-dev-192 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 32 · chunk 112 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: numeric
- Motivo de la propuesta: Actualización periódica no mencionada; compatible pero no inferible.
- Premisa: Confecciona una tabla de coste total de propiedad (CTP) que incluya el coste de la licencia, la formación, la asistencia y la hipotética retirada progresiva del CED. ● Ten en cuenta los gastos ocultos
- Afirmación: La tabla de CTP debe actualizarse cada curso escolar.

## eu-dev-193 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 50 · chunk 175 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: ninguno
- Motivo de la propuesta: Método concreto no mencionado; compatible pero no inferible.
- Premisa: Al igual que ocurre con otros materiales didácticos, deberías considerar distintos métodos para valorar el impacto real del CED elegido en tu práctica docente.
- Afirmación: El impacto debe medirse con pruebas estandarizadas externas.

## eu-dev-194 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Opciones de contenido educativo digital · document_id 1fa0183b… · split dev · página 14 · chunk 50 · rights p.2 (CC BY 4.0) · sha256 831584fc204df9d5…
- Fenómenos: ninguno
- Motivo de la propuesta: Hora semanal no mencionada; compatible pero no inferible.
- Premisa: Lo más importante es mantener una actitud abierta a la exploración y centrarse en aprender durante el proceso, tanto a nivel individual como en equipo.
- Afirmación: Los centros deben dedicar una hora semanal a la exploración de nuevos CED.

## eu-dev-195 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 11 · chunk 15 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: numeric
- Motivo de la propuesta: Fecha, protagonista y propuesta conservados.
- Premisa: El 9 de mayo de 1950, un estadista francés, Robert Schuman, tuvo una genial idea: Alemania Occidental y Francia trabajarían juntas en el sector del carbón y del acero.
- Afirmación: El 9 de mayo de 1950 Schuman propuso que Francia y Alemania Occidental cooperaran en el carbón y el acero.

## eu-dev-196 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 12 · chunk 16 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: «estos seis países» remite a los fundadores citados antes en el documento; fecha y tratado conservados.
- Premisa: El 18 de abril de 1951, estos seis países firman un texto, el Tratado de la Comunidad Europea del Carbón y del Acero (CECA).
- Afirmación: El 18 de abril de 1951 los seis países firmaron el Tratado de la CECA.

## eu-dev-197 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 13 · chunk 18 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: coreference
- Motivo de la propuesta: Símbolo y división conservados.
- Premisa: El muro de Berlín constituye el símbolo de la Guerra Fría, la separación entre el este (comunista) y el oeste (capitalista).
- Afirmación: El muro de Berlín simboliza la Guerra Fría y la división entre el este comunista y el oeste capitalista.

## eu-dev-198 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 42 · chunk 59 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: ninguno
- Motivo de la propuesta: Composición conservada en la paráfrasis.
- Premisa: El Consejo de la Unión Europea o Consejo de Ministros Está compuesto por ministros de los Estados miembros de la Unión.
- Afirmación: El Consejo de la Unión Europea lo forman ministros de los Estados miembros.

## eu-dev-199 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 42 · chunk 60 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: ninguno
- Motivo de la propuesta: Composición conservada; formato de título del folleto intacto.
- Premisa: El Consejo Europeo : la reunión de los dirigentes de los países europeos El Consejo Europeo reúne a los jefes de Estado o de Gobierno de los Estados miembros de la Unión.
- Afirmación: El Consejo Europeo reúne a los jefes de Estado o de Gobierno de los Estados miembros.

## eu-dev-200 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 46 · chunk 66 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: coreference
- Motivo de la propuesta: Tres libertades conservadas.
- Premisa: De este modo, cada persona que viva en un país de la Unión Europea es libre de circular, residir y trabajar en otro país de la Unión.
- Afirmación: Quien vive en la UE puede circular, residir y trabajar libremente en otro país de la Unión.

## eu-dev-201 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 47 · chunk 69 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: ninguno
- Motivo de la propuesta: Origen del símbolo conservado.
- Premisa: El símbolo del euro (€) proviene de la letra griega épsilon y hace referencia a la primera letra de la palabra «Europa».
- Afirmación: El símbolo € deriva de la épsilon griega, inicial de Europa.

## eu-dev-202 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 29 · chunk 38 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: numeric
- Motivo de la propuesta: Año distinto (2040 frente a 2050).
- Premisa: El objetivo es que, como muy tarde en 2050, Europa sea el primer continente climáticamente neutro del mundo.
- Afirmación: Europa será el primer continente climáticamente neutro como muy tarde en 2040.

## eu-dev-203 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 34 · chunk 51 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: negation
- Motivo de la propuesta: La premisa lo prohíbe («nunca»); la afirmación lo permite.
- Premisa: prudencia: nunca comuniques información demasiado personal a tus nuevos «amigos», y todavía menos a los que casi no conoces.
- Afirmación: Puedes compartir datos muy personales con desconocidos en internet.

## eu-dev-204 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 36 · chunk 53 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: ninguno
- Motivo de la propuesta: «millones» frente a «nadie».
- Premisa: En todo el planeta, millones de personas se ven afectadas cada año por catástrofes naturales, conflictos o guerras.
- Afirmación: Nadie se ve afectado por catástrofes naturales, conflictos o guerras.

## eu-dev-205 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 46 · chunk 68 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: negation,numeric
- Motivo de la propuesta: Cifra distinta (20 frente a 29).
- Premisa: El espacio Schengen agrupa a 29 países: 25 países de la Unión Europea y cuatro países no pertenecientes a la Unión.
- Afirmación: El espacio Schengen agrupa a 20 países.

## eu-dev-206 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 44 · chunk 64 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: coreference
- Motivo de la propuesta: Sede distinta (Bruselas frente a Luxemburgo). Primera frase del pasaje extraído.
- Premisa: El Tribunal de Justicia tiene su sede en Luxemburgo.
- Afirmación: El Tribunal de Justicia tiene su sede en Bruselas.

## eu-dev-207 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 30 · chunk 43 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: coreference
- Motivo de la propuesta: La premisa exige que vivan de sus tierras; la afirmación propone su abandono.
- Premisa: Había que producir alimentos suficientes para todos y asegurarse de que los agricultores pudiesen vivir de sus tierras.
- Afirmación: La PAC busca que los agricultores abandonen sus tierras.

## eu-dev-208 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 34 · chunk 49 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: ninguno
- Motivo de la propuesta: Conducta opuesta (indiferencia frente a respeto).
- Premisa: RESPETO Trata a los otros como desearías que te trataran a ti: sé agradable y trátalos con respeto.
- Afirmación: Trata a los otros con indiferencia.

## eu-dev-209 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 26 · chunk 32 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: negation,coreference
- Motivo de la propuesta: «este premio» remite al premio tratado en la página; periodicidad y sede no mencionadas. Compatible pero no inferible.
- Premisa: Decidió destinar los fondos de este premio a los niños que no tuvieron la suerte de crecer en un contexto de paz.
- Afirmación: El premio se entrega cada dos años en Oslo.

## eu-dev-210 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 27 · chunk 34 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: ninguno
- Motivo de la propuesta: Umbral de reciclaje no mencionado; compatible pero no inferible.
- Premisa: El desarrollo sostenible es una forma de consumo más respetuosa: satisfacemos nuestras necesidades actuales, sin olvidarnos de los que vendrán después de nosotros.
- Afirmación: El desarrollo sostenible exige reciclar al menos el 70 % de los residuos.

## eu-dev-211 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 28 · chunk 37 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: ninguno
- Motivo de la propuesta: Liderazgo de España no mencionado; compatible pero no inferible.
- Premisa: Afortunadamente, desde hace unos años, reciclamos grandes cantidades de productos.
- Afirmación: España recicla más que ningún otro país de la UE.

## eu-dev-212 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 29 · chunk 40 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: ninguno
- Motivo de la propuesta: Cifra por árbol no mencionada; compatible pero no inferible.
- Premisa: Gracias a la clorofila, las plantas verdes absorben los gases de efecto invernadero y expulsan oxígeno.
- Afirmación: Un árbol adulto absorbe unos 20 kilos de CO2 al año.

## eu-dev-213 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 49 · chunk 72 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: ninguno
- Motivo de la propuesta: Porcentaje concreto no mencionado; compatible pero no inferible.
- Premisa: La mayor parte del presupuesto de la Unión Europea proviene de los países de la Unión Europea.
- Afirmación: Cada país aporta el 1 % de su PIB al presupuesto.

## eu-dev-214 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Europa, mejor juntos · document_id 7eee7159… · split dev · página 50 · chunk 73 · rights p.2 (CC BY 4.0) · sha256 8ae48a1c8387cf7b…
- Fenómenos: numeric
- Motivo de la propuesta: Proyecto concreto no mencionado; compatible pero no inferible.
- Premisa: A lo largo de los años, cientos de miles de proyectos se han beneficiado de las inversiones de la Unión Europea.
- Afirmación: El proyecto número 100 000 fue un puente en Polonia.

## eu-dev-215 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 4 · chunk 7 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Fecha de inicio, organizador y fondo conservados.
- Premisa: Desde 2019, los Premios a la Inspiración Rural (Rural Inspiration Awards, RIA) 2021 ( 1) de la Red Europea de Desarrollo Rural (REDR) han destacado los proyectos que utilizan la financiación del Fondo Europeo Agrícola de
- Afirmación: Desde 2019, los RIA 2021 de la REDR distinguen proyectos financiados por el Feader que contribuyen al desarrollo rural.

## eu-dev-216 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 4 · chunk 11 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Número de categorías y primera de ellas conservados; viñeta unida como «:».
- Premisa: El concurso de los RIA 2021 incluyó cuatro categorías temáticas: • Futuros ecológicos: proyectos o iniciativas destinados a abordar o mitigar el cambio climático, demostrar la sostenibilidad y contribuir a la recuperació
- Afirmación: Los RIA 2021 tuvieron cuatro categorías, entre ellas Futuros ecológicos, sobre clima y sostenibilidad rural.

## eu-dev-217 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 7 · chunk 27 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Certificado, año y otorgante conservados.
- Premisa: La explotación agrícola cuenta con un certificado Lubuskie Pearl of Tourism 2018 de la Organización Turística de Lubuskie LOTUR.
- Afirmación: La explotación tiene el certificado Lubuskie Pearl of Tourism 2018 de la organización LOTUR.

## eu-dev-218 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 9 · chunk 40 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Contraste mayoría/minoría y horquilla 5-10 % conservados.
- Premisa: La mayoría de los bosques se recuperan de forma natural, mientras que entre el 5 y el 10 % requieren la replantación de retoños de árboles silvestres.
- Afirmación: La mayor parte del bosque se regenera solo; entre el 5 y el 10 % necesita replantar retoños silvestres.

## eu-dev-219 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 15 · chunk 82 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Dos cifras (100 agricultores, 20 000 mediciones) conservadas.
- Premisa: Más de 100 agricultores midieron la salinización de las aguas superficiales en diferentes ramas del sistema hídrico, lo que dio lugar a más de 20 000 mediciones.
- Afirmación: Más de un centenar de agricultores tomaron más de 20 000 mediciones de salinización.

## eu-dev-220 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 20 · chunk 113 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Cuatro efectos conservados, incluido el número de empleos.
- Premisa: El proceso reduce los costes para Josenea, ha diversificado la actividad empresarial y generado tres nuevos empleos, al tiempo que también contribuye al secuestro de carbono y a la reducción de las emisiones de gases de 
- Afirmación: El proceso de Josenea bajó costes, diversificó el negocio, creó tres empleos y ayuda a capturar carbono.

## eu-dev-221 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 7 · chunk 24 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: negation
- Motivo de la propuesta: La premisa demuestra lo contrario con un caso sin formación agraria.
- Premisa: La familia quería demostrar que incluso sin educación agrícola era posible fundar una explotación agrícola desde cero en un pequeño pueblo, en un suelo poco fértil, en un período de tiempo breve.
- Afirmación: Solo con un título agrícola se puede fundar una explotación.

## eu-dev-222 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 8 · chunk 35 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: coreference
- Motivo de la propuesta: La premisa afirma disminuirlo significativamente; la afirmación lo aumenta.
- Premisa: Las raíces, los brotes y las hojas disminuyen significativamente el riesgo de erosión, mientras que el cultivo también proporciona combustible para su planta de biogás.
- Afirmación: El cultivo aumenta el riesgo de erosión del suelo.

## eu-dev-223 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 10 · chunk 47 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Cifra distinta (17 frente a 174).
- Premisa: Los componentes de transferencia de conocimientos importantes fueron 174 días de formación y visitas de demostración con expertos locales e internacionales.
- Afirmación: La transferencia de conocimientos sumó 17 días de formación y visitas.

## eu-dev-224 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 13 · chunk 66 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Orden de magnitud distinto (10 frente a 100).
- Premisa: Se ofrecieron aproximadamente 100 jornadas de formación, servicio y formación con tutores.
- Afirmación: Se ofrecieron unas 10 jornadas de formación.

## eu-dev-225 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 16 · chunk 90 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Límite distinto (50 frente a 5).
- Premisa: Para promover el bienestar de las abejas, un plan inicial gratuito para un máximo de 5 colonias permite que las personas prueben los registros apícolas digitales a pequeña escala antes de invertir en la aplicación.
- Afirmación: El plan inicial gratuito cubre hasta 50 colonias.

## eu-dev-226 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 25 · chunk 152 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Número de municipios distinto (19 frente a 9).
- Premisa: En 2021 se extenderá a 9 municipios de la región de la Mosela, con 30 000 habitantes más.
- Afirmación: En 2021 el proyecto ya cubría 19 municipios de la Mosela.

## eu-dev-227 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 28 · chunk 168 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Periodo distinto (2015-2020 frente a 2018-2023).
- Premisa: La medida 16 (Cooperación) del programa de desarrollo rural (PDR) se utiliza para respaldar las actividades del proyecto entre 2018 y 2023.
- Afirmación: La medida 16 respalda actividades del proyecto entre 2015 y 2020.

## eu-dev-228 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 12 · chunk 63 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: ninguno
- Motivo de la propuesta: Descargas no mencionadas; compatible pero no inferible. Referencia de página interna conservada.
- Premisa: El proyecto «BeeKing» de Letonia (página 14) pretende potenciar el bienestar de las colonias de abejas mediante una aplicación digital que ayuda a los apicultores a gestionar y realizar un seguimiento de las colonias de 
- Afirmación: La aplicación BeeKing supera las 10 000 descargas.

## eu-dev-229 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 16 · chunk 87 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Extensión a Estonia no mencionada; compatible pero no inferible.
- Premisa: Gracias al apoyo de la medida 19 (Leader/Desarrollo local participativo) del programa de desarrollo rural (PDR) letón, el proyecto «BeeKing» potencia el bienestar de las colonias de abejas, ofrece asistencia en la gestió
- Afirmación: El proyecto BeeKing se extenderá a Estonia en 2026.

## eu-dev-230 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 17 · chunk 94 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Coste no mencionado; compatible pero no inferible.
- Premisa: Una encuesta de aproximadamente un millar de posibles clientes aclaró la posible demanda.
- Afirmación: La encuesta costó 20 000 euros.

## eu-dev-231 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 17 · chunk 97 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: ninguno
- Motivo de la propuesta: Austria no mencionada; compatible pero no inferible.
- Premisa: Para muchos agricultores, HofladenBOX se ha convertido en un canal de distribución importante que ayuda a conservar empleos en la agricultura regional.
- Afirmación: HofladenBOX opera también en Austria.

## eu-dev-232 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 21 · chunk 122 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: coreference
- Motivo de la propuesta: Número de comercios no mencionado; compatible pero no inferible.
- Premisa: Los comerciantes han mejorado su gama de productos regionales y han aprendido sobre la promoción y la colocación del producto dentro del comercio.
- Afirmación: La red incluye más de 200 comercios.

## eu-dev-233 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 24 · chunk 142 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: numeric
- Motivo de la propuesta: Dotación no mencionada; compatible pero no inferible.
- Premisa: Esta categoría de los RIA 2021 incluye ejemplos de proyectos que promueven el diálogo intergeneracional y la transferencia de conocimientos entre generaciones en beneficio de toda la comunidad.
- Afirmación: Esta categoría reparte un millón de euros en premios.

## eu-dev-234 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Premios a la inspiración rural 2021 · document_id a18b60ce… · split dev · página 24 · chunk 145 · rights p.2 (Reutilización con atribución indicada en el PDF) · sha256 fe58e88954eb526f…
- Fenómenos: ninguno
- Motivo de la propuesta: Región concreta no mencionada; compatible pero no inferible.
- Premisa: La financiación del Feader está ayudando a resolver los problemas de movilidad y acceso a los servicios públicos en una región aislada de Francia.
- Afirmación: La región francesa beneficiada es Córcega.

## eu-dev-235 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 12 · chunk 15 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Fecha y objeto del pacto conservados.
- Premisa: En septiembre de 2024, los líderes mundiales adoptaron el Pacto para el Futuro, que incluye compromisos para proteger las necesidades de las generaciones futuras y garantizar que las decisiones se tomen teniendo en cuent
- Afirmación: En septiembre de 2024 se adoptó el Pacto para el Futuro, con compromisos para proteger a las generaciones futuras.

## eu-dev-236 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 15 · chunk 29 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Número 24 y destinatario conservados.
- Premisa: Para ello, unidos en la diversidad, redactamos veinticuatro recomendaciones dirigidas a la Comisión Europea.
- Afirmación: Redactaron veinticuatro recomendaciones para la Comisión Europea, unidos en la diversidad.

## eu-dev-237 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 29 · chunk 76 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: coreference
- Motivo de la propuesta: Doble dirección del intercambio conservada.
- Premisa: El apoyo al aprendizaje intergeneracional garantiza que los jóvenes puedan ayudar a las personas mayores con las competencias digitales, mientras que las personas mayores comparten su sabiduría, cerrando así la brecha di
- Afirmación: El aprendizaje intergeneracional permite a jóvenes ayudar a mayores en lo digital y a mayores compartir sabiduría.

## eu-dev-238 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 32 · chunk 100 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: ninguno
- Motivo de la propuesta: Objeto de la recomendación F y medios (planificación, agricultores, sistemas resilientes) conservados. Primera frase completa del pasaje.
- Premisa: En beneficio de las generaciones presentes y futuras, y para consolidar la equidad intergeneracional, recomendamos establecer políticas integrales para garantizar la seguridad y la soberanía alimentarias de la UE mediant
- Afirmación: Recomiendan políticas integrales para la seguridad y soberanía alimentarias de la UE.

## eu-dev-239 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 34 · chunk 116 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Dos elementos y selección aleatoria conservados.
- Premisa: Este mecanismo deberá constar de dos elementos: 1) un órgano de expertos, compuesto por especialistas en equidad intergeneracional para garantizar un debate basado en hechos, y 2) un cuerpo de ciudadanos, compuesto por p
- Afirmación: El mecanismo tendrá un órgano de expertos y un cuerpo de ciudadanos elegidos al azar.

## eu-dev-240 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 37 · chunk 137 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: coreference
- Motivo de la propuesta: Gratuidad, universalidad y aprendizaje permanente conservados.
- Premisa: Garantizar una educación gratuita para todos y que permita a las personas aprender múltiples profesiones a lo largo de su vida.
- Afirmación: Educación gratuita para todos que permita aprender varias profesiones durante la vida.

## eu-dev-241 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 38 · chunk 148 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: ninguno
- Motivo de la propuesta: Paráfrasis fiel de derecho y regulación.
- Premisa: El acceso a la energía debe reconocerse como un derecho universal y regularse como un bien público.
- Afirmación: La energía debe ser un derecho universal regulado como bien público.

## eu-dev-242 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 46 · chunk 210 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: coreference
- Motivo de la propuesta: Medios (cooperación, aprendizaje) y fin (equidad) conservados.
- Premisa: De este modo, las necesidades de cada generación pueden satisfacerse mediante la cooperación y el aprendizaje compartido centrado en la equidad entre generaciones.
- Afirmación: Las necesidades de cada generación se satisfacen con cooperación y aprendizaje compartido en equidad.

## eu-dev-243 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 15 · chunk 26 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: negation,coreference
- Motivo de la propuesta: La premisa exige no empeorar; la afirmación lo permite. Se omite el marcador de nota «2».
- Premisa: En muchos sentidos, esta es la prueba de equidad más veraz: que las decisiones adoptadas hoy mejoren o, al menos, no empeoren la vida de quienes nos sucedan y de quienes sucedan a estos.
- Afirmación: Las decisiones de hoy pueden empeorar la vida de las generaciones futuras sin problema.

## eu-dev-244 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 31 · chunk 92 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa pide aumentarlo; la afirmación pide reducirlo.
- Premisa: Recomendamos que la UE aumente el apoyo financiero a los agricultores locales y regionales, tanto actuales como futuros, para ayudarles a adoptar y ampliar prácticas agrícolas sostenibles.
- Afirmación: Recomiendan reducir el apoyo financiero a los agricultores locales.

## eu-dev-245 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 33 · chunk 112 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: negation
- Motivo de la propuesta: La premisa afirma que no la tienen; la afirmación dice que sí.
- Premisa: Es esencial garantizar que los intereses de las generaciones futuras, que actualmente no tienen voz en la toma de decisiones, se tengan en cuenta de forma sistemática.
- Afirmación: Las generaciones futuras ya tienen voz en la toma de decisiones.

## eu-dev-246 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 35 · chunk 125 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa exige facultar y exigir la intervención; la afirmación la rechaza.
- Premisa: Debe facultarse a los gobiernos locales para que intervengan contra las subidas especulativas de los precios del suelo y la vivienda, y debe exigirse que lo hagan.
- Afirmación: Los gobiernos locales no deben intervenir en los precios de la vivienda.

## eu-dev-247 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 38 · chunk 145 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa exige remunerarlo; la afirmación lo niega.
- Premisa: Debe remunerarse a los padres que se quedan en casa y a los abuelos por el trabajo que realizan en el cuidado de los hijos.
- Afirmación: El cuidado de hijos por padres y abuelos no debe remunerarse.

## eu-dev-248 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 40 · chunk 164 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa propone crearlo; la afirmación lo rechaza.
- Premisa: A largo plazo, crear un fondo de renta básica y un fondo de pensiones dotado de ingresos fiscales basados en el aumento de la productividad que aporta la IA para garantizar una distribución justa y la paz social.
- Afirmación: Rechazan crear ningún fondo de renta básica.

## eu-dev-249 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 47 · chunk 215 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: ninguno
- Motivo de la propuesta: Efecto invertido (aumentará frente a menos).
- Premisa: Prestar más atención a las generaciones presentes y futuras en términos de salud mental se traducirá en una sociedad que sufre menos problemas de salud mental.
- Afirmación: Atender la salud mental aumentará los problemas de salud mental.

## eu-dev-250 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 36 · chunk 134 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: ninguno
- Motivo de la propuesta: Porcentaje presupuestario no mencionado; compatible pero no inferible.
- Premisa: Una buena educación es la base del desarrollo personal y social.
- Afirmación: La educación concentra el 10 % del presupuesto de la UE.

## eu-dev-251 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 38 · chunk 151 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: ninguno
- Motivo de la propuesta: Recorte de defensa no mencionado; compatible pero no inferible.
- Premisa: Debemos reorganizar los presupuestos para dar prioridad a una energía más limpia y establecer un plan a largo plazo tanto a nivel nacional como de la UE.
- Afirmación: Los presupuestos de defensa se reducirán un 5 % para financiar la energía.

## eu-dev-252 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 43 · chunk 184 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: ninguno
- Motivo de la propuesta: Examen no mencionado; compatible pero no inferible.
- Premisa: Los valores humanistas (empatía, tolerancia, solidaridad, etc.) también deben integrarse en los procesos de aprendizaje de los europeos.
- Afirmación: Estos valores se evaluarán en un examen europeo anual.

## eu-dev-253 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 45 · chunk 198 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: ninguno
- Motivo de la propuesta: Plazo no mencionado; compatible pero no inferible.
- Premisa: Los migrantes deben tener trabajo para disponer de medios que les permitan vivir en condiciones adecuadas.
- Afirmación: El permiso de trabajo se concederá en un plazo máximo de tres meses.

## eu-dev-254 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 46 · chunk 206 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: coreference
- Motivo de la propuesta: Proporción concreta no mencionada; compatible pero no inferible. Primera frase del pasaje.
- Premisa: Al mismo tiempo, las personas mayores sufren soledad y a veces carecen de un papel digno en la sociedad.
- Afirmación: Uno de cada tres mayores vive solo.

## eu-dev-255 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 41 · chunk 168 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: ninguno
- Motivo de la propuesta: Grupo afectado no mencionado; compatible pero no inferible.
- Premisa: Esto deja margen para la manipulación a través de noticias falsas y burbujas de información.
- Afirmación: Las burbujas de información afectan sobre todo a los mayores de 65 años.

## eu-dev-256 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: Panel europeo de ciudadanos sobre equidad intergeneracional · document_id f12b6c43… · split dev · página 14 · chunk 19 · rights p.2 (CC BY 4.0) · sha256 a544f83b0dcebacc…
- Fenómenos: coreference
- Motivo de la propuesta: Calendario y sede no mencionados; compatible pero no inferible.
- Premisa: Nosotros mismos representábamos a distintas generaciones, desde adolescentes hasta personas octogenarias, y nuestros intercambios de opiniones reflejaron tanto la riqueza como las tensiones propias de la diversidad geogr
- Afirmación: El panel se reunió durante tres fines de semana en Bruselas.

## eu-dev-257 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 4 · chunk 7 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: ninguno
- Motivo de la propuesta: Seis criterios conservados en la paráfrasis.
- Premisa: Esto significa que los profesores deben ser capaces de evaluar el uso de la IA con espíritu crítico, teniendo en cuenta la equidad, la diversidad, la transparencia, el bienestar, la privacidad y la seguridad.
- Afirmación: Los docentes deben valorar críticamente la IA atendiendo a la equidad, la diversidad, la transparencia, el bienestar, la privacidad y la seguridad.

## eu-dev-258 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 8 · chunk 26 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: coreference
- Motivo de la propuesta: Tres garantías conservadas; se omite el encabezado posterior del documento.
- Premisa: La inclusión de la ética en este ámbito refleja un compromiso más profundo para garantizar que los usos educativos de la IA respeten la dignidad humana, promuevan la equidad y preserven la integridad del aprendizaje, en 
- Afirmación: La ética educativa de la IA debe respetar la dignidad humana, promover la equidad y preservar la integridad del aprendizaje según los valores de la UE.

## eu-dev-259 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 16 · chunk 69 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: ninguno
- Motivo de la propuesta: Paráfrasis fiel sin cifras ni negación.
- Premisa: En la Unión de las Competencias, la educación digital es un factor clave para el desarrollo del capital humano de Europa.
- Afirmación: La educación digital es clave para el capital humano europeo en la Unión de las Competencias.

## eu-dev-260 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 17 · chunk 75 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: numeric
- Motivo de la propuesta: Papel pionero y año 2024 conservados; se omite el título repetido del documento.
- Premisa: La Unión Europea ha asumido un papel pionero a escala mundial en la regulación de la IA a través del Reglamento de Inteligencia Artificial de la UE (2024).
- Afirmación: La UE lidera mundialmente la regulación de la IA con su Reglamento de 2024.

## eu-dev-261 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 34 · chunk 173 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: ninguno
- Motivo de la propuesta: Recomendación de pilotaje conservada; primera frase del pasaje («Llevar a cabo una experiencia piloto...») omitida por ser título.
- Premisa: Antes de introducir nuevas herramientas de IA en el centro educativo, puede ser útil probar el sistema con una determinada cohorte de aprendientes.
- Afirmación: Conviene pilotar la herramienta de IA con un grupo de aprendientes antes de implantarla en el centro.

## eu-dev-262 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 36 · chunk 189 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: ninguno
- Motivo de la propuesta: Vínculo alfabetización-competencia y motivo conservados.
- Premisa: También reconoce que la alfabetización en materia de IA está estrechamente vinculada a una competencia digital más amplia, dada la creciente presencia de la IA en herramientas, plataformas y servicios cotidianos.
- Afirmación: La alfabetización en IA está ligada a la competencia digital general por la presencia creciente de la IA en la vida cotidiana.

## eu-dev-263 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 39 · chunk 209 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: coreference
- Motivo de la propuesta: Tres aplicaciones conservadas.
- Premisa: Estos conocimientos pueden facilitar el desarrollo de estrategias de aprendizaje personalizadas, observaciones adaptativas sobre el rendimiento y sistemas de intervención temprana adaptados a cada aprendiente.
- Afirmación: Esos conocimientos facilitan estrategias personalizadas, observación adaptativa e intervención temprana por aprendiente.

## eu-dev-264 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 10 · chunk 36 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: coreference
- Motivo de la propuesta: La premisa advierte de que pueden reforzarlas; la afirmación dice que las reducen.
- Premisa: Cuando se utilizan en las aulas, estas herramientas pueden reforzar involuntariamente las desigualdades existentes o malinterpretar las necesidades de los estudiantes, en particular de aquellos procedentes de entornos in
- Afirmación: En las aulas, estas herramientas reducen las desigualdades existentes.

## eu-dev-265 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 18 · chunk 82 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: negation,coreference
- Motivo de la propuesta: La premisa lo prohíbe en ese caso; la afirmación lo permite.
- Premisa: En cambio, si un centro educativo obliga a los estudiantes a utilizar la aplicación, el uso de dicho sistema de reconocimiento de emociones está prohibido.
- Afirmación: Si el centro obliga a usar la aplicación, el reconocimiento de emociones está permitido.

## eu-dev-266 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 19 · chunk 88 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: negation,coreference
- Motivo de la propuesta: La premisa limita los riesgos; la afirmación los declara graves.
- Premisa: La naturaleza de esas tareas es tan restringida y limitada que solo presentan riesgos limitados que no aumentan por la utilización de un sistema de IA en un contexto que un anexo al Reglamento recoja como uso de alto rie
- Afirmación: Esas tareas presentan riesgos graves.

## eu-dev-267 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 20 · chunk 96 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa recoge este uso en el anexo de alto riesgo; la afirmación lo excluye.
- Premisa: Sistemas de IA destinados a ser utilizados para evaluar los resultados del aprendizaje, también cuando dichos resultados se utilicen para orientar el proceso de aprendizaje de las personas físicas en centros educativos y
- Afirmación: La evaluación del aprendizaje con IA no se considera un uso de alto riesgo.

## eu-dev-268 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 37 · chunk 195 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa atribuye decisión y secuencias a los agentes; la afirmación los reduce a respuesta simple.
- Premisa: A diferencia de las herramientas de IA básicas que responden a una única entrada, los agentes pueden tomar decisiones, establecer secuencias de acciones y llevar a cabo flujos de trabajo en nombre de un usuario u otro si
- Afirmación: Los agentes solo responden a una entrada sin tomar decisiones.

## eu-dev-269 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 38 · chunk 199 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: negation,coreference
- Motivo de la propuesta: La premisa distingue patrones de hechos; la afirmación los declara hechos.
- Premisa: Hablar sobre las alucinaciones puede ayudar a los estudiantes a profundizar en su conocimiento de la IA porque comprenden que los resultados se generan a partir de patrones, no de hechos, y porque aprenden a cuestionar y
- Afirmación: Los resultados de la IA son hechos verificados.

## eu-dev-270 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 42 · chunk 223 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: negation
- Motivo de la propuesta: La premisa afirma la mejora; la afirmación la niega.
- Premisa: La RAG hace que las respuestas de la IA tengan una base más factual y sean más fiables sin necesidad de reciclar todo el modelo.
- Afirmación: La RAG no mejora la base factual de las respuestas.

## eu-dev-271 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 12 · chunk 41 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: coreference
- Motivo de la propuesta: Porcentaje de jornada no mencionado; compatible pero no inferible.
- Premisa: Las herramientas de IA tienen potencial para mejorar las prácticas de enseñanza, aprendizaje y evaluación, y para ayudar a los directores de centros educativos a mejorar la forma en que planifican, organizan y gestionan 
- Afirmación: Los directores dedican el 20 % de su jornada a gestionar la IA.

## eu-dev-272 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 14 · chunk 57 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: ninguno
- Motivo de la propuesta: Número de lenguas no mencionado; compatible pero no inferible.
- Premisa: Aprender lenguas extranjeras para utilizar aplicaciones de IA que adapten el vocabulario, la pronunciación y las tareas gramaticales al nivel y al progreso de cada aprendiente.
- Afirmación: Estas aplicaciones cubren más de veinte lenguas.

## eu-dev-273 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 20 · chunk 101 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: numeric
- Motivo de la propuesta: Periodicidad no mencionada; compatible pero no inferible.
- Premisa: Además, el artículo 27 del Reglamento de IA exige a las instituciones educativas, como responsables del despliegue de sistemas de IA, que lleven a cabo una evaluación de impacto relativa a los derechos fundamentales (EID
- Afirmación: La evaluación de impacto debe repetirse cada dos años.

## eu-dev-274 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 21 · chunk 106 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: ninguno
- Motivo de la propuesta: Votación no mencionada; compatible pero no inferible.
- Premisa: La elección justificada se refiere al uso de conocimientos, hechos y datos para justificar las elecciones colectivas necesarias o adecuadas por parte de múltiples partes interesadas en el entorno escolar.
- Afirmación: La elección justificada exige una votación del claustro.

## eu-dev-275 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 29 · chunk 148 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: coreference
- Motivo de la propuesta: Decisión final y fecha no mencionadas; compatible pero no inferible. Se omite el fragmento previo del encabezado.
- Premisa: Un centro estudia la posibilidad de permitir que los estudiantes utilicen un modelo lingüístico de uso general (LLM, por sus siglas en inglés) como apoyo en sus tareas y proyectos.
- Afirmación: El centro autorizó finalmente el uso del LLM en 2025.

## eu-dev-276 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 34 · chunk 178 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: coreference
- Motivo de la propuesta: Exclusión por edad concreta no mencionada; compatible pero no inferible.
- Premisa: Es posible que los aprendientes, según su edad, necesiten distintos enfoques para captar su interés de modo que puedan participar en la toma de decisiones con conocimiento de causa.
- Afirmación: Los menores de 12 años no participan en ninguna decisión.

## eu-dev-277 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 40 · chunk 214 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: negation
- Motivo de la propuesta: Revisión trimestral no mencionada; compatible pero no inferible.
- Premisa: Ayuda a que las decisiones basadas en la IA se mantengan centradas en la calidad, la pertinencia y la equidad del aprendizaje, en lugar de regirse por defecto por parámetros como el tiempo de interacción o la popularidad
- Afirmación: Los parámetros de popularidad se revisan cada trimestre.

## eu-dev-278 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: IA ética en la enseñanza · document_id f692aa0b… · split dev · página 41 · chunk 219 · rights p.2 (CC BY 4.0) · sha256 ab6a2720ed22ba04…
- Fenómenos: ninguno
- Motivo de la propuesta: Niveles concretos no mencionados; compatible pero no inferible. «Esos niveles» remite a la premisa.
- Premisa: En la educación, los datos se utilizan para apoyar la enseñanza, el aprendizaje y la toma de decisiones a múltiples niveles.
- Afirmación: Esos niveles incluyen el aula, el centro, la región y el Estado.

## eu-dev-279 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 11 · chunk 19 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: numeric
- Motivo de la propuesta: Fecha, sujeto y cifra conservados en la paráfrasis.
- Premisa: Desde 2022, los Estados miembros han acogido a más de cuatro millones de personas.
- Afirmación: Desde 2022, los Estados miembros han recibido a más de cuatro millones de personas.

## eu-dev-280 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 14 · chunk 27 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: ninguno
- Motivo de la propuesta: Competencia y destinatarios conservados; el pasaje continúa en el fragmento contiguo.
- Premisa: El tribunal estará facultado para exigir responsabilidades a los dirigentes políticos y militares rusos, que son los principales responsables de las atrocidades cometidas en Ucrania.
- Afirmación: El tribunal podrá pedir cuentas a los dirigentes políticos y militares rusos, principales responsables de las atrocidades en Ucrania.

## eu-dev-281 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 15 · chunk 33 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: numeric
- Motivo de la propuesta: Fecha de creación y doble flujo conservados.
- Premisa: Los corredores de solidaridad, creados en mayo de 2022, siguen garantizando que Ucrania pueda importar las mercancías que necesita y exportar algunos productos agrícolas y de otro tipo.
- Afirmación: Los corredores de solidaridad, creados en mayo de 2022, permiten a Ucrania importar lo necesario y exportar productos agrícolas y otros.

## eu-dev-282 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 19 · chunk 48 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: numeric
- Motivo de la propuesta: Fecha de adopción y ordinal conservados.
- Premisa: En julio se aprobó la adopción del euro por parte de Bulgaria a partir del 1 de enero de 2026, lo que la convierte en el vigésimo primer Estado miembro de la zona del euro.
- Afirmación: Bulgaria adoptará el euro el 1 de enero de 2026 y será el 21.º miembro de la eurozona.

## eu-dev-283 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 26 · chunk 81 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Dos cifras (2,2 y 15 millones) y horizonte conservados.
- Premisa: Se espera que estos proyectos produzcan casi 2,2 millones de toneladas de hidrógeno renovable a lo largo de diez años, lo que evitará la emisión de 15 millones de toneladas de dióxido de carbono.
- Afirmación: Esos proyectos generarán casi 2,2 millones de toneladas de hidrógeno renovable en diez años y evitarán 15 millones de toneladas de CO2.

## eu-dev-284 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 30 · chunk 101 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: numeric
- Motivo de la propuesta: Mes, plan y cifra conservados.
- Premisa: En abril se publicó el Plan de Acción «Continente de IA», que establece planes para desarrollar gigafactorías de IA equipadas con más de cien mil procesadores avanzados.
- Afirmación: El Plan «Continente de IA», publicado en abril, prevé gigafactorías con más de cien mil procesadores avanzados.

## eu-dev-285 — propuesta IA: supported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 75 · chunk 260 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: ninguno
- Motivo de la propuesta: Fecha de adopción y doble objetivo conservados.
- Premisa: La Estrategia Europea de Resiliencia Hídrica, adoptada en junio, tiene por objeto restaurar y proteger el ciclo del agua, construir una economía hidrointeligente para impulsar la competitividad, y garantizar un agua limp
- Afirmación: La Estrategia de Resiliencia Hídrica, adoptada en junio, busca restaurar el ciclo del agua y garantizar agua limpia y asequible para todos.

## eu-dev-286 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 16 · chunk 36 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: numeric
- Motivo de la propuesta: Cifra distinta (3 900 frente a 6 900 millones). El pasaje abarca dos fragmentos contiguos del mismo texto.
- Premisa: Hasta la fecha, se han asignado 6 900 millones de euros para financiar programas de inversión que benefician directamente a la población de Ucrania: creando nuevos puestos de trabajo, suministrando electricidad, calefacc
- Afirmación: Se han asignado 3 900 millones de euros a programas de inversión para Ucrania.

## eu-dev-287 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 24 · chunk 73 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: numeric
- Motivo de la propuesta: Umbral distinto (2 frente a 1,5 °C).
- Premisa: El Acuerdo pone en marcha un Acelerador Global de Implementación y la iniciativa «Misión Belém para 1,5 °C», con el fin de fomentar compromisos climáticos más sólidos y ayudar a los países a poner en práctica sus planes 
- Afirmación: La iniciativa se llama «Misión Belém para 2 °C».

## eu-dev-288 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 25 · chunk 75 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: ninguno
- Motivo de la propuesta: Mes distinto (junio frente a febrero). Primera frase del pasaje extraído.
- Premisa: En febrero, la Comisión presentó el Plan de Acción para una Energía Asequible, que introduce medidas a corto plazo para reducir los costes de la energía anticipando los beneficios de las energías renovables, el ahorro de
- Afirmación: El Plan de Acción para una Energía Asequible se presentó en junio.

## eu-dev-289 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 26 · chunk 81 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: numeric
- Motivo de la propuesta: Número de proyectos distinto (5 frente a 15).
- Premisa: Se concedieron casi 1 000 millones de euros, con cargo al Fondo de Innovación, financiado a través de los ingresos del régimen de comercio de derechos de emisión de la UE, a 15 proyectos de hidrógeno renovable.
- Afirmación: El Fondo de Innovación financió 5 proyectos de hidrógeno renovable.

## eu-dev-290 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 27 · chunk 83 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: numeric,coreference
- Motivo de la propuesta: Año distinto (2028 frente a 2026).
- Premisa: Para acelerar su transición hacia la circularidad, la UE anunció que propondría una Ley de Economía Circular en 2026, sobre la base del segundo Plan de Acción para la Economía Circular.
- Afirmación: La Ley de Economía Circular se propondrá en 2028.

## eu-dev-291 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 28 · chunk 90 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: ninguno
- Motivo de la propuesta: La premisa apoya sintéticos; la afirmación, fósiles.
- Premisa: Como iniciativa clave en el marco del Plan, se puso en marcha una coalición de Estados miembros pioneros para apoyar la producción y la adopción de combustibles de aviación sintéticos.
- Afirmación: La coalición apoya la producción de combustibles fósiles para la aviación.

## eu-dev-292 — propuesta IA: contradicted (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 35 · chunk 119 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: numeric
- Motivo de la propuesta: Cifra distinta (2 frente a 1,5 billones). Segunda frase del pasaje; se omite el título.
- Premisa: Las ciencias de la vida aportan casi 1,5 billones de euros a la economía de la UE y garantizan 29 millones de puestos de trabajo.
- Afirmación: Las ciencias de la vida aportan casi 2 billones de euros a la economía de la UE.

## eu-dev-293 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 16 · chunk 39 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: ninguno
- Motivo de la propuesta: Reforma concreta no mencionada; compatible pero no inferible.
- Premisa: Más allá de la financiación directa, la UE se está centrando en las reformas estructurales e institucionales como parte del proceso de reconstrucción.
- Afirmación: Las reformas incluyen un nuevo código fiscal.

## eu-dev-294 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 27 · chunk 87 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: ninguno
- Motivo de la propuesta: Tasa concreta no mencionada; compatible pero no inferible.
- Premisa: Una evaluación de la Directiva sobre residuos de aparatos eléctricos y electrónicos puso de relieve las lagunas existentes en la recogida de residuos electrónicos, la valorización de materias primas fundamentales y los r
- Afirmación: La recogida de residuos electrónicos supera el 60 %.

## eu-dev-295 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 29 · chunk 96 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: ninguno
- Motivo de la propuesta: Industria naval no mencionada; compatible pero no inferible. Primera frase del pasaje.
- Premisa: La transición limpia y digital de la industria automovilística cuenta además con el apoyo de la investigación y la innovación.
- Afirmación: El memorando incluye también a la industria naval.

## eu-dev-296 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 30 · chunk 99 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: ninguno
- Motivo de la propuesta: Proyecto y fecha concretos no mencionados; compatible pero no inferible. Última frase del pasaje.
- Premisa: La competitividad a largo plazo de la UE depende del liderazgo en tecnologías críticas como la supercomputación, la inteligencia artificial (IA) y la computación cuántica.
- Afirmación: La UE construirá un ordenador cuántico en 2027.

## eu-dev-297 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 32 · chunk 106 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: coreference
- Motivo de la propuesta: Presupuesto no mencionado; compatible pero no inferible.
- Premisa: La economía espacial, que abarca todas las actividades económicas posibilitadas por las tecnologías y los datos espaciales, desde la infraestructura de satélites hasta los servicios que dependen de ella, es otro ámbito e
- Afirmación: El presupuesto espacial supera los 20 000 millones.

## eu-dev-298 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 36 · chunk 122 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: ninguno
- Motivo de la propuesta: Sede no mencionada; compatible pero no inferible.
- Premisa: También se creó un nuevo centro de biotecnología y biofabricación, para ayudar a las empresas innovadoras, en particular a las empresas emergentes y a las pymes, a comercializar nuevos productos e ideas.
- Afirmación: El centro estará ubicado en Barcelona.

## eu-dev-299 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 34 · chunk 117 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: negation,coreference
- Motivo de la propuesta: Presupuesto no mencionado; compatible pero no inferible. «esas infraestructuras» remite a la premisa.
- Premisa: La Estrategia Europea sobre Infraestructuras de Investigación y Tecnológicas, puesta en marcha recientemente, facilitará la puesta en común de recursos, ayudará a evitar duplicaciones y reforzará la accesibilidad y la co
- Afirmación: El presupuesto conjunto de esas infraestructuras es de 5 000 millones.

## eu-dev-300 — propuesta IA: unsupported (PENDIENTE de revisión)
- Fuente: La UE en 2025 · document_id a43004fd… · split dev · página 66-67 · chunk 231 · rights p.4 (CC BY 4.0) · sha256 d736f4f51d17e89d…
- Fenómenos: ninguno
- Motivo de la propuesta: Causa no mencionada; compatible pero no inferible.
- Premisa: La aceptación social de las personas LGBTIQ+ ha aumentado en toda la UE en los últimos cinco años.
- Afirmación: El aumento se debe a una campaña europea de 2023.
