import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

(() => {
  const canvas = document.querySelector("#library-canvas");
  const dataNode = document.querySelector("#library-books-data");
  if (!(canvas instanceof HTMLCanvasElement) || !dataNode) return;

  const loadState = document.querySelector("#world-load-state");
  const fallbackMessage = document.querySelector("#world-webgl-fallback");
  const bookPanel = document.querySelector("#world-book-panel");
  const pageControls = document.querySelector("#world-page-controls");
  const bookSearch = document.querySelector("#world-search");
  const archiveSearch = document.querySelector("#catalogue-search");
  const alphabet = document.querySelector("#world-alphabet-letters");
  const collections = document.querySelector("#world-collections");
  const homeButton = document.querySelector("#world-home");
  const panelCloseButton = document.querySelector("#world-close-book");
  const readingButton = document.querySelector("#world-toggle-reading");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const motionDuration = reducedMotion ? 180 : 1250;

  let books;
  try {
    books = JSON.parse(dataNode.textContent || "[]");
  } catch (error) {
    console.error("The interactive library could not read its book collection.", error);
    showFallback();
    return;
  }

  const booksByCategory = new Map();
  for (const book of books) {
    const list = booksByCategory.get(book.category) || [];
    list.push(book);
    booksByCategory.set(book.category, list);
  }

  let scene;
  let camera;
  let renderer;
  let controls;
  let resizeObserver;
  let readerModel = null;
  let readerTimer = null;
  let activeBook = null;
  let activeShelf = null;
  let activeLetter = null;
  let filterText = "";
  let hoveredBook = null;
  let cameraMove = null;
  let pointerStart = null;
  const shelves = [];
  const clickableShelves = [];
  const clickableBooks = [];
  const booksById = new Map();
  const textureLoader = new THREE.TextureLoader();
  textureLoader.setCrossOrigin("anonymous");
  const coverTextures = new Map();
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const worldDirection = new THREE.Vector3();
  const initialCameraPosition = new THREE.Vector3(0, 2.6, 10.8);
  const initialTarget = new THREE.Vector3(0, 2, -3.4);
  const clock = new THREE.Clock();

  function showFallback() {
    if (loadState) loadState.hidden = true;
    if (fallbackMessage) fallbackMessage.hidden = false;
    canvas.setAttribute("aria-label", "La scène 3D est indisponible. Retrouvez tous les livres dans l’index de la bibliothèque.");
  }

  function init() {
    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: true,
        alpha: false,
        powerPreference: "high-performance",
      });
    } catch (error) {
      console.error("WebGL could not initialize the interactive library.", error);
      showFallback();
      return;
    }

    scene = new THREE.Scene();
    scene.background = new THREE.Color("#17110d");
    scene.fog = new THREE.FogExp2("#17110d", 0.023);
    camera = new THREE.PerspectiveCamera(42, 1, 0.1, 75);
    camera.position.copy(initialCameraPosition);
    camera.lookAt(initialTarget);

    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.18;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));

    controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(initialTarget);
    controls.enableDamping = true;
    controls.dampingFactor = 0.055;
    controls.enablePan = true;
    controls.minDistance = 4;
    controls.maxDistance = 22;
    controls.minPolarAngle = Math.PI * 0.16;
    controls.maxPolarAngle = Math.PI * 0.49;
    controls.rotateSpeed = 0.55;
    controls.panSpeed = 0.45;
    controls.zoomSpeed = 0.75;

    buildRoom();
    buildLibraryShelves();
    buildDust();
    buildAlphabet();
    bindInteractions();
    const initialChip = collections?.querySelector(".world-collection-chip.is-active[data-shelf]");
    activeShelf = initialChip?.dataset.shelf && initialChip.dataset.shelf !== "__all__"
      ? initialChip.dataset.shelf
      : null;
    filterText = bookSearch?.value.trim().toLocaleLowerCase("fr") || "";
    updateFilters();
    const initialShelf = shelves.find((shelf) => shelf.category === activeShelf);
    if (initialShelf) focusShelf(initialShelf);
    resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas.parentElement);
    resize();
    renderer.setAnimationLoop(animate);

    window.addEventListener("pagehide", dispose, { once: true });
    window.addEventListener("keydown", onKeyDown);
    canvas.addEventListener("webglcontextlost", onContextLost, false);
    requestAnimationFrame(() => loadState?.classList.add("is-loaded"));
  }

  function woodTexture() {
    const size = 512;
    const source = document.createElement("canvas");
    source.width = size;
    source.height = size;
    const context = source.getContext("2d");
    const base = context.createLinearGradient(0, 0, size, size);
    base.addColorStop(0, "#7b5030");
    base.addColorStop(0.48, "#674027");
    base.addColorStop(1, "#8a5a32");
    context.fillStyle = base;
    context.fillRect(0, 0, size, size);
    for (let index = 0; index < 130; index += 1) {
      const x = Math.random() * size;
      const width = 1 + Math.random() * 7;
      context.fillStyle = Math.random() > 0.5 ? "rgba(241,194,127,.065)" : "rgba(25,13,9,.09)";
      context.fillRect(x, 0, width, size);
    }
    for (let index = 0; index < 22; index += 1) {
      const x = Math.random() * size;
      const y = Math.random() * size;
      context.strokeStyle = "rgba(28,15,9,.12)";
      context.lineWidth = 2 + Math.random() * 5;
      context.beginPath();
      context.ellipse(x, y, 4 + Math.random() * 14, 2 + Math.random() * 7, 0, 0, Math.PI * 2);
      context.stroke();
    }
    const texture = new THREE.CanvasTexture(source);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }

  function surfaceNormalTexture(strength, frequency = 0.2) {
    const source = document.createElement("canvas");
    source.width = 128;
    source.height = 128;
    const context = source.getContext("2d");
    const image = context.createImageData(128, 128);
    for (let y = 0; y < 128; y += 1) {
      for (let x = 0; x < 128; x += 1) {
        const index = (y * 128 + x) * 4;
        const nx = Math.sin(x * frequency + Math.sin(y * frequency * 0.23) * 2.5) * strength;
        const ny = Math.cos(y * frequency + Math.sin(x * frequency * 0.18) * 2) * strength * 0.55;
        image.data[index] = Math.max(0, Math.min(255, 128 - nx));
        image.data[index + 1] = Math.max(0, Math.min(255, 128 - ny));
        image.data[index + 2] = 252;
        image.data[index + 3] = 255;
      }
    }
    context.putImageData(image, 0, 0);
    const texture = new THREE.CanvasTexture(source);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    return texture;
  }

  function stoneTexture() {
    const source = document.createElement("canvas");
    source.width = 256;
    source.height = 256;
    const context = source.getContext("2d");
    context.fillStyle = "#42352a";
    context.fillRect(0, 0, 256, 256);
    for (let index = 0; index < 460; index += 1) {
      const shade = Math.floor(52 + Math.random() * 76);
      context.fillStyle = `rgba(${shade},${shade - 6},${shade - 14},${0.04 + Math.random() * 0.12})`;
      context.beginPath();
      context.ellipse(
        Math.random() * 256,
        Math.random() * 256,
        1 + Math.random() * 16,
        1 + Math.random() * 8,
        Math.random() * Math.PI,
        0,
        Math.PI * 2,
      );
      context.fill();
    }
    const texture = new THREE.CanvasTexture(source);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    return texture;
  }

  function carpetTexture() {
    const size = 512;
    const source = document.createElement("canvas");
    source.width = size;
    source.height = size;
    const context = source.getContext("2d");
    context.fillStyle = "#39201a";
    context.fillRect(0, 0, size, size);
    context.fillStyle = "#633727";
    context.fillRect(24, 24, size - 48, size - 48);
    context.strokeStyle = "#c69b58";
    context.lineWidth = 3;
    context.strokeRect(38, 38, size - 76, size - 76);
    context.strokeStyle = "rgba(221,184,111,.58)";
    context.lineWidth = 1;
    context.strokeRect(49, 49, size - 98, size - 98);
    for (let index = 0; index < 20; index += 1) {
      const offset = 64 + index * 20;
      context.fillStyle = index % 2 ? "#b89452" : "#c6a567";
      context.save();
      context.translate(size / 2, offset);
      context.rotate(Math.PI / 4);
      context.fillRect(-5, -5, 10, 10);
      context.restore();
      context.save();
      context.translate(size / 2, size - offset);
      context.rotate(Math.PI / 4);
      context.fillRect(-5, -5, 10, 10);
      context.restore();
    }
    for (let row = 0; row < 7; row += 1) {
      for (let column = 0; column < 7; column += 1) {
        const x = 112 + column * 48;
        const y = 112 + row * 48;
        if (x > 405 || y > 405) continue;
        context.strokeStyle = (row + column) % 2 ? "rgba(215,176,99,.3)" : "rgba(29,15,14,.32)";
        context.lineWidth = 2;
        context.beginPath();
        context.moveTo(x, y - 10);
        context.lineTo(x + 10, y);
        context.lineTo(x, y + 10);
        context.lineTo(x - 10, y);
        context.closePath();
        context.stroke();
      }
    }
    const texture = new THREE.CanvasTexture(source);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }

  function addBox(parent, name, size, position, material, castShadow = true) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), material);
    mesh.name = name;
    mesh.position.set(...position);
    mesh.castShadow = castShadow;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }

  function addLight(color, intensity, position, distance, decay = 1.6) {
    const light = new THREE.PointLight(color, intensity, distance, decay);
    light.position.set(...position);
    light.castShadow = false;
    scene.add(light);
    return light;
  }

  function createSpineTexture(book, color) {
    const source = document.createElement("canvas");
    source.width = 192;
    source.height = 384;
    const context = source.getContext("2d");
    context.scale(0.75, 0.75);
    context.fillStyle = color;
    context.fillRect(0, 0, source.width, source.height);
    const shade = context.createLinearGradient(0, 0, source.width, 0);
    shade.addColorStop(0, "rgba(0,0,0,.35)");
    shade.addColorStop(0.18, "rgba(255,230,177,.12)");
    shade.addColorStop(0.74, "rgba(0,0,0,.08)");
    shade.addColorStop(1, "rgba(0,0,0,.35)");
    context.fillStyle = shade;
    context.fillRect(0, 0, source.width, source.height);
    context.strokeStyle = "rgba(221,186,118,.86)";
    context.lineWidth = 3;
    context.strokeRect(14, 13, source.width - 28, source.height - 26);
    context.strokeStyle = "rgba(244,215,164,.57)";
    context.lineWidth = 1;
    context.strokeRect(19, 20, source.width - 38, source.height - 40);
    context.fillStyle = "#f4e3bf";
    context.textAlign = "center";
    context.font = "600 19px Georgia";
    context.fillText(String(book.volume || "✦"), source.width / 2, 55);
    context.save();
    context.translate(source.width / 2, source.height / 2);
    context.rotate(-Math.PI / 2);
    context.font = `600 ${Math.max(20, Math.min(29, 1800 / Math.max(12, book.title.length)))}px Georgia`;
    context.fillStyle = "#fff1d2";
    context.fillText(book.title.toLocaleUpperCase("fr"), 0, 7, 410);
    context.restore();
    context.fillStyle = "rgba(244,224,190,.88)";
    context.font = "14px Georgia";
    context.fillText(String(book.author).slice(0, 24), source.width / 2, source.height - 32);
    const texture = new THREE.CanvasTexture(source);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }

  function hashString(value) {
    let hash = 2166136261;
    for (let index = 0; index < value.length; index += 1) {
      hash ^= value.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function illustratedCoverTexture(book) {
    const source = document.createElement("canvas");
    source.width = 192;
    source.height = 288;
    const context = source.getContext("2d");
    context.scale(0.5, 0.5);
    const seed = hashString(`${book.category}:${book.title}:${book.author}`);
    const palettes = {
      fantasy: ["#20382f", "#54714a", "#d9b677"],
      science_fiction: ["#182a3b", "#287187", "#d0b77d"],
      philosophy: ["#332936", "#745473", "#d9c198"],
      history: ["#3b2b20", "#956443", "#e0c58f"],
      psychology: ["#28313b", "#68808a", "#e3c88e"],
      literature: ["#35272a", "#8d5048", "#e1c49a"],
      mystery: ["#222832", "#665d63", "#d2ab6d"],
      romance: ["#382530", "#a55865", "#ebca99"],
      computer_science: ["#202a2e", "#55766c", "#d4bd7b"],
      mathematics: ["#222b45", "#5b6b9b", "#d7c58c"],
      science: ["#1d3335", "#548477", "#d7bb7f"],
    };
    const [dark, accent, gold] = palettes[book.category] || palettes.fantasy;
    const gradient = context.createLinearGradient(0, 0, 384, 576);
    gradient.addColorStop(0, dark);
    gradient.addColorStop(1, accent);
    context.fillStyle = gradient;
    context.fillRect(0, 0, 384, 576);
    const light = context.createRadialGradient(
      192 + (seed % 80) - 40,
      235 + ((seed >>> 7) % 70) - 35,
      5,
      192,
      250,
      250,
    );
    light.addColorStop(0, `${gold}66`);
    light.addColorStop(1, `${dark}00`);
    context.fillStyle = light;
    context.fillRect(0, 0, 384, 576);
    context.strokeStyle = `${gold}bb`;
    context.lineWidth = 3;
    context.strokeRect(17, 17, 350, 542);
    context.lineWidth = 1;
    context.strokeRect(25, 25, 334, 526);

    const motifX = 105 + (seed % 174);
    const motifY = 210 + ((seed >>> 8) % 128);
    context.save();
    context.translate(motifX, motifY);
    context.rotate((seed % 8) * Math.PI / 16);
    context.strokeStyle = `${gold}88`;
    context.lineWidth = 2;
    for (let ring = 0; ring < 4; ring += 1) {
      context.beginPath();
      context.arc(0, 0, 22 + ring * 22, 0, Math.PI * 2);
      context.stroke();
    }
    for (let ray = 0; ray < 8; ray += 1) {
      context.rotate(Math.PI / 4);
      context.beginPath();
      context.moveTo(-92, 0);
      context.lineTo(92, 0);
      context.stroke();
    }
    context.restore();

    context.fillStyle = gold;
    context.textAlign = "center";
    context.font = "600 12px Arial";
    context.letterSpacing = "2px";
    context.fillText(String(book.category_label || "MNÉMOSYNE").toLocaleUpperCase("fr"), 192, 83, 300);
    context.fillStyle = "#fff4dc";
    context.font = `600 ${book.title.length > 27 ? 22 : book.title.length > 18 ? 26 : 31}px Georgia`;
    const titleLines = [];
    let line = "";
    for (const word of book.title.split(" ")) {
      const candidate = line ? `${line} ${word}` : word;
      if (line && context.measureText(candidate).width > 310) {
        titleLines.push(line);
        line = word;
      } else {
        line = candidate;
      }
    }
    if (line) titleLines.push(line);
    const titleY = 145 + (4 - Math.min(titleLines.length, 4)) * 14;
    titleLines.slice(0, 4).forEach((titleLine, index) => {
      context.fillText(titleLine, 192, titleY + index * 36, 320);
    });
    context.strokeStyle = `${gold}aa`;
    context.beginPath();
    context.moveTo(75, 490);
    context.lineTo(309, 490);
    context.stroke();
    context.fillStyle = "#f3e5c8";
    context.font = "17px Georgia";
    context.fillText(book.author, 192, 522, 300);
    const texture = new THREE.CanvasTexture(source);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }

  function coverTexture(book) {
    const key = book.id;
    if (coverTextures.has(key)) return coverTextures.get(key);
    if (!book.cover || book.cover.startsWith("/livres/")) {
      const texture = illustratedCoverTexture(book);
      coverTextures.set(key, texture);
      return texture;
    }
    const texture = textureLoader.load(
      book.cover,
      (loadedTexture) => {
        loadedTexture.colorSpace = THREE.SRGBColorSpace;
        loadedTexture.anisotropy = renderer.capabilities.getMaxAnisotropy();
      },
      undefined,
      () => {
        const fallback = illustratedCoverTexture(book);
        texture.image = fallback.image;
        texture.needsUpdate = true;
        fallback.dispose();
      },
    );
    coverTextures.set(key, texture);
    return texture;
  }

  function pageTexture(book, pageNumber, reverse = false) {
    const source = document.createElement("canvas");
    source.width = 420;
    source.height = 620;
    const context = source.getContext("2d");
    const paper = context.createLinearGradient(0, 0, source.width, source.height);
    paper.addColorStop(0, "#f5ebd6");
    paper.addColorStop(0.5, "#ede0c6");
    paper.addColorStop(1, "#e4d3b5");
    context.fillStyle = paper;
    context.fillRect(0, 0, source.width, source.height);
    context.strokeStyle = "rgba(135,99,59,.13)";
    context.lineWidth = 2;
    context.strokeRect(20, 20, source.width - 40, source.height - 40);
    context.textAlign = "center";
    context.fillStyle = "#7b603e";
    context.font = "16px Georgia";
    context.fillText(reverse ? "MNÉMOSYNE · LE CABINET" : "SPÉCIMEN DE LECTURE", source.width / 2, 64);
    context.strokeStyle = "rgba(164,125,74,.5)";
    context.beginPath();
    context.moveTo(70, 83);
    context.lineTo(source.width - 70, 83);
    context.stroke();
    context.textAlign = "left";
    context.fillStyle = "#4c392d";
    context.font = "600 22px Georgia";
    context.fillText(String(book.title).slice(0, 27), 48, 132, source.width - 96);
    context.font = "16px Georgia";
    context.fillStyle = "#755e45";
    context.fillText(String(book.author).slice(0, 34), 48, 162, source.width - 96);
    context.fillStyle = "#78674f";
    context.font = "16px Georgia";
    const notice = reverse
      ? "Ouvrez un autre rayon pour choisir votre prochaine lecture."
      : "Ceci est une page d'exemple originale, créée pour vous faire découvrir le livre en trois dimensions.";
    const lines = wrapText(context, notice, source.width - 100);
    lines.forEach((line, index) => context.fillText(line, 48, 222 + index * 26));
    context.fillStyle = "#927a59";
    context.font = "italic 15px Georgia";
    context.fillText("Le texte de cette œuvre n'est pas reproduit ici.", 48, 332, source.width - 96);
    context.textAlign = "center";
    context.font = "14px Georgia";
    context.fillText(String(pageNumber).padStart(2, "0"), source.width / 2, source.height - 45);
    const texture = new THREE.CanvasTexture(source);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }

  function wrapText(context, text, maxWidth) {
    const words = text.split(" ");
    const lines = [];
    let line = "";
    for (const word of words) {
      const testLine = line ? `${line} ${word}` : word;
      if (line && context.measureText(testLine).width > maxWidth) {
        lines.push(line);
        line = word;
      } else {
        line = testLine;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  function buildRoom() {
    const wood = woodTexture();
    const woodNormal = surfaceNormalTexture(13, 0.17);
    scene.userData.woodTexture = wood;
    scene.userData.woodNormalTexture = woodNormal;
    const stoneMap = stoneTexture();
    const stoneNormal = surfaceNormalTexture(8, 0.34);
    const woodMaterial = new THREE.MeshStandardMaterial({
      map: wood,
      normalMap: woodNormal,
      normalScale: new THREE.Vector2(0.21, 0.17),
      color: 0xc3a17b,
      roughness: 0.74,
      metalness: 0.03,
    });
    const darkWood = new THREE.MeshStandardMaterial({ color: 0x39251a, roughness: 0.62, map: wood });
    const stone = new THREE.MeshStandardMaterial({
      color: 0xb5a28b,
      map: stoneMap,
      normalMap: stoneNormal,
      normalScale: new THREE.Vector2(0.18, 0.18),
      roughness: 0.94,
    });
    const floorTexture = wood.clone();
    floorTexture.repeat.set(8, 11);
    floorTexture.needsUpdate = true;
    const floorMaterial = new THREE.MeshStandardMaterial({ map: floorTexture, color: 0x94744f, roughness: 0.72 });
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(28, 32), floorMaterial);
    floor.name = "Parquet en noyer";
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(0, -0.08, -1.5);
    floor.receiveShadow = true;
    scene.add(floor);

    const rugTexture = carpetTexture();
    rugTexture.repeat.set(2, 3);
    const rug = new THREE.Mesh(
      new THREE.PlaneGeometry(13, 19),
      new THREE.MeshStandardMaterial({
        map: rugTexture,
        normalMap: surfaceNormalTexture(9, 0.38),
        normalScale: new THREE.Vector2(0.14, 0.14),
        roughness: 0.98,
      }),
    );
    rug.name = "Tapis persan";
    rug.rotation.x = -Math.PI / 2;
    rug.position.set(0, -0.035, -1.2);
    rug.receiveShadow = true;
    scene.add(rug);

    addBox(scene, "Mur de fond en pierre", [27, 8, 0.45], [0, 4, -12.9], stone, false);
    addBox(scene, "Mur gauche", [0.45, 8, 27], [-12.9, 4, 0], stone, false);
    addBox(scene, "Mur droit", [0.45, 8, 27], [12.9, 4, 0], stone, false);
    addBox(scene, "Plafond ombragé", [26, 0.5, 27], [0, 8, -0.5], darkWood, false);

    for (let index = 0; index < 6; index += 1) {
      const x = -10.2 + index * 4.08;
      const pilaster = addBox(scene, `Pilastre arrière ${index + 1}`, [0.23, 7.6, 0.48], [x, 3.8, -12.47], woodMaterial, false);
      pilaster.castShadow = false;
      const capital = addBox(scene, `Chapiteau ${index + 1}`, [0.53, 0.17, 0.8], [x, 7.48, -12.43], darkWood, false);
      capital.castShadow = false;
    }
    for (const x of [-12.46, 12.46]) {
      for (let index = 0; index < 6; index += 1) {
        const z = -10 + index * 4;
        addBox(scene, "Pilastre de galerie", [0.48, 7.5, 0.22], [x, 3.8, z], woodMaterial, false);
        addBox(scene, "Chapiteau de galerie", [0.8, 0.16, 0.51], [x, 7.45, z], darkWood, false);
      }
    }

    scene.add(new THREE.HemisphereLight("#f0d7ac", "#21160f", 1.2));
    const ambient = new THREE.AmbientLight("#ddb980", 0.48);
    scene.add(ambient);
    const keyLight = new THREE.DirectionalLight("#f8dcae", 2.3);
    keyLight.position.set(-5, 8, 4);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1024, 1024);
    keyLight.shadow.camera.left = -17;
    keyLight.shadow.camera.right = 17;
    keyLight.shadow.camera.top = 15;
    keyLight.shadow.camera.bottom = -15;
    keyLight.shadow.bias = -0.0003;
    scene.add(keyLight);

    addLight("#ffc77e", 70, [-7.3, 5.7, 1], 13);
    addLight("#f4bd75", 75, [6.8, 5.6, -2.6], 15);
    addLight("#e7ab60", 82, [0.3, 5.9, -8.7], 13);
    addLight("#ffe0a2", 28, [-1, 6.6, 5.2], 11);

    for (const x of [-7, -2.5, 2.3, 7.1]) {
      addBox(
        scene,
        "Lanterne en cuivre",
        [0.14, 0.08, 0.14],
        [x, 6.25, -2.5],
        new THREE.MeshStandardMaterial({
          color: 0xe7bd7d,
          emissive: "#c27b35",
          emissiveIntensity: 1.6,
          roughness: 0.35,
          metalness: 0.55,
        }),
        false,
      );
      addLight("#ffc877", 25, [x, 5.8, -2.5], 5, 1.8);
    }

    for (let index = 0; index < 9; index += 1) {
      const z = 6 - index * 2.2;
      addBox(scene, "Garde-corps de galerie", [0.09, 0.95, 0.09], [-10.2, 4.15, z], woodMaterial, false);
      addBox(scene, "Garde-corps de galerie", [0.09, 0.95, 0.09], [10.2, 4.15, z], woodMaterial, false);
    }
    addBox(scene, "Main courante", [0.12, 0.11, 18.5], [-10.2, 4.65, -2.7], darkWood, false);
    addBox(scene, "Main courante", [0.12, 0.11, 18.5], [10.2, 4.65, -2.7], darkWood, false);
    buildReadingNook(woodMaterial, darkWood);
  }

  function buildReadingNook(wood, darkWood) {
    const leather = new THREE.MeshStandardMaterial({ color: "#542d27", roughness: 0.88 });
    const cushion = new THREE.MeshStandardMaterial({ color: "#74503a", roughness: 0.96 });
    const bronze = new THREE.MeshStandardMaterial({ color: "#b08a54", roughness: 0.32, metalness: 0.7 });

    function armchair(x, z, rotation) {
      const chair = new THREE.Group();
      chair.name = "Fauteuil de lecture en cuir";
      chair.position.set(x, 0.02, z);
      chair.rotation.y = rotation;
      scene.add(chair);
      for (const legX of [-0.31, 0.31]) {
        for (const legZ of [-0.27, 0.27]) {
          addBox(chair, "Pied tourné", [0.075, 0.47, 0.075], [legX, 0.24, legZ], darkWood);
        }
      }
      addBox(chair, "Assise sculptée", [0.84, 0.2, 0.82], [0, 0.57, 0], leather);
      addBox(chair, "Coussin d'assise", [0.7, 0.15, 0.66], [0, 0.7, 0.02], cushion);
      const back = addBox(chair, "Dossier capitonné", [0.84, 0.82, 0.19], [0, 1.03, -0.31], leather);
      back.rotation.x = -0.08;
      for (const armX of [-0.46, 0.46]) {
        addBox(chair, "Accoudoir rembourré", [0.16, 0.14, 0.7], [armX, 0.91, -0.015], leather);
        addBox(chair, "Montant d'accoudoir", [0.11, 0.34, 0.11], [armX, 0.73, 0.25], darkWood);
        addBox(chair, "Montant d'accoudoir", [0.11, 0.34, 0.11], [armX, 0.73, -0.3], darkWood);
      }
      return chair;
    }

    armchair(-4.2, 1.1, Math.PI / 5);
    armchair(4.55, -0.4, -Math.PI / 3.2);
    armchair(-4.8, -3.2, Math.PI / 3.8);

    const table = new THREE.Group();
    table.name = "Table de lecture en noyer";
    table.position.set(0.8, 0, 1.8);
    scene.add(table);
    const tabletop = new THREE.Mesh(new THREE.CylinderGeometry(0.82, 0.86, 0.14, 48), wood);
    tabletop.position.y = 0.86;
    tabletop.castShadow = true;
    tabletop.receiveShadow = true;
    table.add(tabletop);
    const apron = new THREE.Mesh(new THREE.CylinderGeometry(0.51, 0.55, 0.18, 32), darkWood);
    apron.position.y = 0.72;
    table.add(apron);
    const pedestal = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.34, 0.64, 20), bronze);
    pedestal.position.y = 0.38;
    table.add(pedestal);
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.52, 0.6, 0.1, 32), darkWood);
    base.position.y = 0.08;
    table.add(base);

    const lampStem = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.04, 0.45, 12), bronze);
    lampStem.position.set(0, 1.14, 0);
    table.add(lampStem);
    const lampShade = new THREE.Mesh(
      new THREE.ConeGeometry(0.25, 0.22, 24, 1, true),
      new THREE.MeshStandardMaterial({
        color: "#c5a36d",
        emissive: "#c1843d",
        emissiveIntensity: 0.5,
        roughness: 0.52,
        side: THREE.DoubleSide,
      }),
    );
    lampShade.position.set(0, 1.43, 0);
    table.add(lampShade);
    const tableLight = new THREE.PointLight("#ffd38b", 32, 6, 1.7);
    tableLight.position.set(0, 1.52, 0);
    table.add(tableLight);

    const globe = new THREE.Group();
    globe.name = "Globe céleste sur pied";
    globe.position.set(-2.2, 0, -0.7);
    scene.add(globe);
    const globeSphere = new THREE.Mesh(
      new THREE.SphereGeometry(0.36, 24, 20),
      new THREE.MeshStandardMaterial({ color: "#6b7b68", roughness: 0.82, metalness: 0.04 }),
    );
    globeSphere.position.y = 1.25;
    globe.add(globeSphere);
    const axis = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.045, 1.05, 12), bronze);
    axis.position.y = 0.72;
    globe.add(axis);
    const baseStand = new THREE.Mesh(new THREE.CylinderGeometry(0.23, 0.28, 0.12, 24), darkWood);
    baseStand.position.y = 0.12;
    globe.add(baseStand);

    for (const [x, z] of [[-5.8, -1.3], [6.1, 1.4], [2.4, -5.8]]) {
      const vase = new THREE.Group();
      vase.name = "Vase en céramique";
      vase.position.set(x, 0, z);
      const body = new THREE.Mesh(
        new THREE.SphereGeometry(0.28, 20, 16),
        new THREE.MeshStandardMaterial({ color: "#765340", roughness: 0.45, metalness: 0.2 }),
      );
      body.scale.set(1, 1.27, 1);
      body.position.y = 0.35;
      vase.add(body);
      const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.11, 0.17, 0.34, 18), bronze);
      neck.position.y = 0.67;
      vase.add(neck);
      scene.add(vase);
    }
  }

  function createSpine(book, index) {
    const palettes = {
      fantasy: ["#6e2923", "#345443", "#925f32", "#573346"],
      science_fiction: ["#29384e", "#287187", "#405865", "#3b4e62"],
      philosophy: ["#49394a", "#735447", "#5f475c", "#716449"],
      history: ["#6a402b", "#8b613d", "#55402b", "#7d4d31"],
      psychology: ["#3d515a", "#6a5945", "#4b5a54", "#79634d"],
      literature: ["#6f3735", "#774c3e", "#5c3c4a", "#8a6343"],
      mystery: ["#303b4b", "#534044", "#4a4b50", "#76533a"],
      romance: ["#803d52", "#764a60", "#9b5b54", "#6a3b44"],
      computer_science: ["#355449", "#4a5961", "#62573b", "#34454a"],
      mathematics: ["#374366", "#625d87", "#3e5564", "#76624a"],
      science: ["#31544e", "#54754d", "#5b6552", "#426474"],
    };
    const categoryPalette = palettes[book.category] || palettes.fantasy;
    const color = categoryPalette[hashString(book.title) % categoryPalette.length];
    const spineTexture = createSpineTexture(book, color);
    const pages = new THREE.MeshStandardMaterial({ color: 0xe0d1b3, roughness: 0.97 });
    const front = new THREE.MeshStandardMaterial({
      map: spineTexture,
      roughness: 0.66,
      metalness: 0.12,
      emissive: "#5b3e20",
      emissiveIntensity: 0,
    });
    const back = new THREE.MeshStandardMaterial({ color, roughness: 0.8 });
    const cover = new THREE.MeshStandardMaterial({
      map: coverTexture(book),
      color: 0xf3e7d4,
      roughness: 0.8,
      emissive: color,
      emissiveIntensity: 0,
    });
    const coverInside = new THREE.MeshStandardMaterial({ color: 0x754b36, roughness: 0.85 });
    const hash = hashString(`${book.title}:${book.author}`);
    const horizontal = hash % 15 === 0;
    const width = horizontal ? 0.46 : 0.135 + (hash % 7) * 0.009;
    const height = horizontal ? 0.105 : 0.55 + ((hash >>> 5) % 9) * 0.023;
    const depth = horizontal ? 0.31 : 0.38 + ((hash >>> 11) % 7) * 0.025;
    const spineBox = new THREE.Mesh(
      new THREE.BoxGeometry(width, height, depth),
      horizontal ? [cover, back, cover, pages, front, back] : [cover, back, pages, pages, front, back],
    );
    spineBox.castShadow = true;
    spineBox.userData.book = book;
    spineBox.userData.materials = [cover, back, pages, front, coverInside];
    spineBox.userData.spineColor = color;
    spineBox.userData.dimensions = { width, height, depth, horizontal };
    spineBox.name = book.title;
    booksById.set(book.id, spineBox);
    clickableBooks.push(spineBox);
    return spineBox;
  }

  function createPlaqueTexture(text) {
    const source = document.createElement("canvas");
    source.width = 512;
    source.height = 140;
    const context = source.getContext("2d");
    const gradient = context.createLinearGradient(0, 0, 0, 140);
    gradient.addColorStop(0, "#bd9660");
    gradient.addColorStop(0.5, "#86613b");
    gradient.addColorStop(1, "#63432b");
    context.fillStyle = gradient;
    context.fillRect(0, 0, 512, 140);
    context.strokeStyle = "#e2c48e";
    context.lineWidth = 5;
    context.strokeRect(10, 10, 492, 120);
    context.fillStyle = "#fff0ce";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.font = "600 34px Georgia";
    const title = text.length > 27 ? `${text.slice(0, 25)}…` : text;
    context.fillText(title, 256, 70, 455);
    const texture = new THREE.CanvasTexture(source);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }

  function buildShelf(category, label, items, index, location, rackNumber) {
    const root = new THREE.Group();
    const plaqueLabel = rackNumber > 1 ? `${label} · ${String.fromCharCode(64 + rackNumber)}` : label;
    root.name = `Rayon ${plaqueLabel}`;
    root.position.set(location.x, 0.12, location.z);
    root.rotation.y = location.rotation;
    root.userData.category = category;
    scene.add(root);

    const caseWidth = 2.42;
    const caseHeight = 4.72;
    const caseDepth = 0.72;
    const timber = new THREE.MeshStandardMaterial({
      map: scene.userData.woodTexture,
      normalMap: scene.userData.woodNormalTexture,
      normalScale: new THREE.Vector2(0.21, 0.17),
      color: 0xd3a878,
      roughness: 0.66,
      metalness: 0.06,
    });
    const darkTimber = new THREE.MeshStandardMaterial({ color: 0x38241a, roughness: 0.64, metalness: 0.03 });
    const gold = new THREE.MeshStandardMaterial({
      color: 0xe0b66f,
      emissive: "#9b682f",
      emissiveIntensity: 0.42,
      roughness: 0.32,
      metalness: 0.6,
    });
    const backboard = addBox(root, "Dos de bibliothèque", [caseWidth, caseHeight, 0.1], [0, caseHeight / 2, -caseDepth / 2], darkTimber);
    backboard.receiveShadow = true;
    addBox(root, "Montant gauche", [0.14, caseHeight, caseDepth], [-caseWidth / 2, caseHeight / 2, 0], timber);
    addBox(root, "Montant droit", [0.14, caseHeight, caseDepth], [caseWidth / 2, caseHeight / 2, 0], timber);
    addBox(root, "Corniche", [caseWidth + 0.19, 0.22, caseDepth + 0.14], [0, caseHeight + 0.07, 0], timber);
    addBox(root, "Socle sculpté", [caseWidth + 0.2, 0.19, caseDepth + 0.16], [0, 0.12, 0], darkTimber);
    addBox(root, "Filet doré", [caseWidth + 0.22, 0.025, caseDepth + 0.17], [0, 0.23, 0.02], gold, false);

    const shelfLevels = [0.25, 1.34, 2.43, 3.52, 4.61];
    for (let level = 0; level < shelfLevels.length; level += 1) {
      const y = shelfLevels[level];
      addBox(root, `Tablette ${level + 1}`, [caseWidth + 0.08, 0.105, caseDepth + 0.1], [0, y, 0.025], timber);
      if (level > 0 && level < shelfLevels.length - 1) {
        const underShelfLight = new THREE.Mesh(
          new THREE.BoxGeometry(caseWidth - 0.22, 0.018, 0.04),
          new THREE.MeshStandardMaterial({
            color: 0xf3cc91,
            emissive: "#eea84d",
            emissiveIntensity: 1.8,
            roughness: 0.35,
          }),
        );
        underShelfLight.position.set(0, y - 0.075, caseDepth / 2 - 0.07);
        root.add(underShelfLight);
      }
    }

    const plaque = new THREE.Mesh(
      new THREE.BoxGeometry(1.46, 0.38, 0.045),
      new THREE.MeshStandardMaterial({ map: createPlaqueTexture(plaqueLabel), roughness: 0.42, metalness: 0.22 }),
    );
    plaque.name = `Enseigne ${plaqueLabel}`;
    plaque.position.set(0, caseHeight + 0.2, caseDepth / 2 + 0.06);
    plaque.userData.shelfCategory = category;
    root.add(plaque);
    clickableShelves.push(plaque);

    const usableWidth = caseWidth - 0.34;
    const rows = [0.82, 1.91, 3.0, 4.09];
    const booksPerRow = Math.ceil(items.length / rows.length);
    rows.forEach((rowY, rowIndex) => {
      const rowBooks = items.slice(rowIndex * booksPerRow, (rowIndex + 1) * booksPerRow);
      const dimensions = rowBooks.map((book) => {
        const hash = hashString(`${book.title}:${book.author}`);
        const horizontal = hash % 15 === 0;
        return {
          horizontal,
          width: horizontal ? 0.46 : 0.135 + (hash % 7) * 0.009,
          height: horizontal ? 0.105 : 0.55 + ((hash >>> 5) % 9) * 0.023,
          depth: horizontal ? 0.31 : 0.38 + ((hash >>> 11) % 7) * 0.025,
        };
      });
      const occupiedWidth = dimensions.reduce((total, size) => total + size.width, 0);
      const gap = Math.max(0.035, (usableWidth - occupiedWidth) / (rowBooks.length + 1));
      let nextX = -usableWidth / 2 + gap;

      rowBooks.forEach((book, bookIndex) => {
        const size = dimensions[bookIndex];
        const bookRoot = new THREE.Group();
        bookRoot.name = book.title;
        bookRoot.position.set(
          nextX + size.width / 2,
          rowY - 0.24 + size.height / 2,
          caseDepth / 2 - size.depth / 2 + 0.11,
        );
        bookRoot.rotation.z = size.horizontal
          ? (bookIndex % 2 ? -0.035 : 0.025)
          : (bookIndex % 2 ? 1 : -1) * (0.012 + (bookIndex % 3) * 0.018);
        bookRoot.rotation.y = ((bookIndex % 3) - 1) * 0.025;
        const mesh = createSpine(book, index * 29 + rowIndex * booksPerRow + bookIndex);
        bookRoot.add(mesh);
        bookRoot.userData.originalPosition = bookRoot.position.clone();
        bookRoot.userData.originalRotation = bookRoot.quaternion.clone();
        bookRoot.userData.originalScale = bookRoot.scale.clone();
        bookRoot.userData.shelf = root;
        bookRoot.userData.hovered = false;
        root.add(bookRoot);
        mesh.userData.bookRoot = bookRoot;
        nextX += size.width + gap;
      });
    });

    const shelfGlow = new THREE.PointLight("#ffbe6c", 2.2, 4.4, 1.7);
    shelfGlow.position.set(0, 3.95, caseDepth / 2 + 0.32);
    shelfGlow.name = "Halo du rayon";
    root.add(shelfGlow);
    root.userData.shelfGlow = shelfGlow;
    const shelf = { root, category, label, books: items, opacity: 1, targetOpacity: 1, index };
    shelves.push(shelf);
    return shelf;
  }

  function shelfLocations(count) {
    const locations = [];
    const backCount = Math.min(8, count);
    const sideCount = Math.ceil((count - backCount) / 2);
    for (let index = 0; index < backCount; index += 1) {
      locations.push({
        x: -8.4 + (index * 16.8) / Math.max(1, backCount - 1),
        z: -11.45,
        rotation: 0,
      });
    }
    for (let index = 0; index < sideCount; index += 1) {
      const z = 6.15 - (index * 14) / Math.max(1, sideCount - 1);
      locations.push({ x: -11.25, z, rotation: Math.PI / 2 });
      locations.push({ x: 11.25, z, rotation: -Math.PI / 2 });
    }
    return locations.slice(0, count);
  }

  function buildLibraryShelves() {
    const labels = new Map(books.map((book) => [book.category, book.category_label]));
    const entries = Array.from(booksByCategory.entries()).sort((left, right) =>
      (labels.get(left[0]) || left[0]).localeCompare(labels.get(right[0]) || right[0], "fr", { sensitivity: "base" }),
    );
    const racks = [];
    for (const [category, items] of entries) {
      const sortedBooks = [...items].sort((left, right) => left.title.localeCompare(right.title, "fr"));
      for (let offset = 0; offset < sortedBooks.length; offset += 24) {
        racks.push({
          category,
          label: labels.get(category) || category,
          items: sortedBooks.slice(offset, offset + 24),
          rackNumber: Math.floor(offset / 24) + 1,
        });
      }
    }
    const locations = shelfLocations(racks.length);
    racks.forEach((rack, index) =>
      buildShelf(rack.category, rack.label, rack.items, index, locations[index], rack.rackNumber),
    );
  }

  function buildDust() {
    const count = 280;
    const positions = new Float32Array(count * 3);
    for (let index = 0; index < count; index += 1) {
      positions[index * 3] = (Math.random() - 0.5) * 22;
      positions[index * 3 + 1] = 0.9 + Math.random() * 5.7;
      positions[index * 3 + 2] = -12 + Math.random() * 22;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const motes = new THREE.Points(
      geometry,
      new THREE.PointsMaterial({
        color: "#ffd997",
        size: 0.032,
        transparent: true,
        opacity: 0.55,
        sizeAttenuation: true,
        depthWrite: false,
      }),
    );
    motes.name = "Poussière dorée dans la lumière";
    scene.add(motes);
    scene.userData.dust = motes;
  }

  function buildAlphabet() {
    const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    for (const letter of letters) {
      const button = document.createElement("button");
      button.className = "world-letter";
      button.type = "button";
      button.textContent = letter;
      button.setAttribute("aria-label", `Rayons commençant par ${letter}`);
      button.dataset.letter = letter;
      const hasCollection = shelves.some((shelf) =>
        shelf.label.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().startsWith(letter),
      );
      button.disabled = !hasCollection;
      button.addEventListener("click", () => selectLetter(letter));
      alphabet.append(button);
    }
  }

  function bindInteractions() {
    collections?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-shelf]");
      if (!(button instanceof HTMLButtonElement) || button.disabled) return;
      selectCollection(button.dataset.shelf);
    });

    bookSearch?.addEventListener("input", () => {
      filterText = bookSearch.value.trim().toLocaleLowerCase("fr");
      if (archiveSearch) archiveSearch.value = bookSearch.value;
      updateFilters();
    });

    archiveSearch?.addEventListener("input", () => {
      if (bookSearch) {
        bookSearch.value = archiveSearch.value;
        filterText = archiveSearch.value.trim().toLocaleLowerCase("fr");
        updateFilters();
      }
    });

    homeButton?.addEventListener("click", returnToHall);
    panelCloseButton?.addEventListener("click", closeSelectedBook);
    readingButton?.addEventListener("click", toggleReading);
    document.querySelector("#world-page-next")?.addEventListener("click", () => turnPage(1));
    document.querySelector("#world-page-previous")?.addEventListener("click", () => turnPage(-1));

    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("pointerup", onPointerUp);
    canvas.addEventListener("pointerleave", onPointerLeave);
    canvas.addEventListener("click", onCanvasClick);
  }

  function matchesBook(book) {
    if (!filterText) return true;
    return `${book.title} ${book.author} ${book.series} ${book.category_label}`.toLocaleLowerCase("fr").includes(filterText);
  }

  function updateFilters() {
    for (const shelf of shelves) {
      const categoryMatches = (!activeShelf || shelf.category === activeShelf) &&
        (!activeLetter || shelf.label.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().startsWith(activeLetter));
      const searchMatches = !filterText || shelf.books.some(matchesBook);
      shelf.targetOpacity = categoryMatches && searchMatches ? 1 : 0.2;
      shelf.root.userData.shelfGlow.intensity = categoryMatches && searchMatches ? 2.2 : 0.35;

      for (const book of shelf.books) {
        const mesh = booksById.get(book.id);
        if (!mesh) continue;
        const isMatch = categoryMatches && matchesBook(book);
        mesh.userData.matching = isMatch;
        const spineMaterial = mesh.material[4];
        spineMaterial.emissive.set(isMatch && filterText ? "#d28a3f" : "#000000");
        spineMaterial.emissiveIntensity = isMatch && filterText ? 0.48 : 0;
      }
    }
    for (const button of alphabet?.querySelectorAll(".world-letter") || []) {
      button.classList.toggle("is-active", button.dataset.letter === activeLetter);
      button.setAttribute("aria-pressed", String(button.dataset.letter === activeLetter));
    }
    for (const button of collections?.querySelectorAll("[data-shelf]") || []) {
      button.classList.toggle("is-active", button.dataset.shelf === (activeShelf || "__all__"));
      if (button.dataset.shelf !== "__all__") {
        button.disabled = !booksByCategory.has(button.dataset.shelf);
      }
    }
    const tip = document.querySelector("#world-interaction-tip");
    if (tip && filterText) {
      const matches = books.filter(matchesBook).length;
      tip.textContent = matches ? `${matches} LIVRE${matches === 1 ? "" : "S"} CORRESPOND${matches === 1 ? "" : "ENT"} À VOTRE RECHERCHE · APPROCHEZ-VOUS` : "AUCUN LIVRE TROUVÉ · MODIFIEZ VOTRE RECHERCHE";
    }
  }

  function selectLetter(letter) {
    activeLetter = activeLetter === letter ? null : letter;
    activeShelf = null;
    updateFilters();
    const first = shelves.find((shelf) =>
      shelf.label.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().startsWith(activeLetter || ""),
    );
    if (first && activeLetter) focusShelf(first);
    else if (!activeLetter) returnToHall();
  }

  function selectCollection(category) {
    if (activeBook) closeSelectedBook();
    activeLetter = null;
    if (category === "__all__") {
      activeShelf = null;
      updateFilters();
      returnToHall();
      return;
    }
    activeShelf = category;
    updateFilters();
    const shelf = shelves.find((candidate) => candidate.category === category);
    if (shelf) focusShelf(shelf);
  }

  function focusShelf(shelf) {
    if (activeBook) closeSelectedBook();
    scene.updateMatrixWorld(true);
    const center = new THREE.Vector3();
    shelf.root.getWorldPosition(center);
    const normal = new THREE.Vector3(0, 0, 1).applyQuaternion(shelf.root.quaternion).normalize();
    const position = center.clone().addScaledVector(normal, 4.2);
    position.y = 2.3;
    center.y = 2.15;
    cameraMoveTo(position, center);
    shelf.root.userData.shelfGlow.intensity = 6;
  }

  function cameraMoveTo(position, target) {
    cameraMove = {
      startPosition: camera.position.clone(),
      endPosition: position.clone(),
      startTarget: controls.target.clone(),
      endTarget: target.clone(),
      elapsed: 0,
      duration: motionDuration,
    };
    controls.enabled = false;
  }

  function returnToHall() {
    if (activeBook) closeSelectedBook();
    activeShelf = null;
    activeLetter = null;
    updateFilters();
    cameraMoveTo(initialCameraPosition, initialTarget);
    hideReader();
  }

  function onPointerDown(event) {
    if (event.button !== 0 && event.pointerType !== "touch") return;
    canvas.dataset.dragged = "false";
    pointerStart = { x: event.clientX, y: event.clientY };
  }

  function onPointerMove(event) {
    if (pointerStart && Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 8) {
      canvas.dataset.dragged = "true";
    }
    setPointer(event);
    const book = intersectingBook();
    if (hoveredBook !== book) {
      if (hoveredBook) hoveredBook.userData.bookRoot.userData.hovered = false;
      hoveredBook = book;
      if (hoveredBook) hoveredBook.userData.bookRoot.userData.hovered = true;
      canvas.style.cursor = hoveredBook ? "pointer" : "grab";
      canvas.setAttribute("aria-label", hoveredBook
        ? `Livre interactif : ${hoveredBook.userData.book.title}. Cliquez pour le prendre et l’ouvrir.`
        : "Explorez la bibliothèque en trois dimensions. Faites glisser pour regarder autour et cliquez sur un rayon pour vous en approcher.");
    }
  }

  function onPointerLeave() {
    if (hoveredBook) hoveredBook.userData.bookRoot.userData.hovered = false;
    hoveredBook = null;
    canvas.style.cursor = "grab";
  }

  function onPointerUp() {
    pointerStart = null;
  }

  function setPointer(event) {
    const bounds = canvas.getBoundingClientRect();
    pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
    pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
  }

  function intersectingBook() {
    if (!camera || activeBook) return null;
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObjects(clickableBooks, false)[0];
    if (!hit) return null;
    const book = hit.object.userData.book;
    return book && matchesBook(book) ? hit.object : null;
  }

  function onCanvasClick(event) {
    if (canvas.dataset.dragged === "true") {
      canvas.dataset.dragged = "false";
      return;
    }
    setPointer(event);
    raycaster.setFromCamera(pointer, camera);
    const bookHit = raycaster.intersectObjects(clickableBooks, false)[0];
    if (bookHit?.object.userData.book && matchesBook(bookHit.object.userData.book)) {
      selectBook(bookHit.object);
      return;
    }
    if (activeBook && !event.target.closest(".world-book-panel, .world-page-controls")) {
      closeSelectedBook();
      return;
    }
    const shelfHit = raycaster.intersectObjects(clickableShelves, false)[0];
    if (shelfHit?.object.userData.shelfCategory) {
      selectCollection(shelfHit.object.userData.shelfCategory);
    }
  }

  function selectBook(mesh) {
    if (activeBook) closeSelectedBook();
    const book = mesh.userData.book;
    const bookRoot = mesh.userData.bookRoot;
    if (!book || !bookRoot) return;

    const shelfRoot = bookRoot.userData.shelf;
    activeBook = { book, mesh, root: bookRoot, shelf: shelfRoot };
    scene.updateMatrixWorld(true);
    const startingPosition = new THREE.Vector3();
    const startingQuaternion = new THREE.Quaternion();
    const startingScale = new THREE.Vector3();
    bookRoot.getWorldPosition(startingPosition);
    bookRoot.getWorldQuaternion(startingQuaternion);
    bookRoot.getWorldScale(startingScale);
    activeBook.originalPosition = bookRoot.userData.originalPosition.clone();
    activeBook.originalRotation = bookRoot.userData.originalRotation.clone();
    activeBook.originalScale = bookRoot.userData.originalScale.clone();
    scene.attach(bookRoot);
    bookRoot.position.copy(startingPosition);
    bookRoot.quaternion.copy(startingQuaternion);
    bookRoot.scale.copy(startingScale);
    activeBook.originalParent = shelfRoot;
    activeBook.targetPosition = camera.position.clone().addScaledVector(camera.getWorldDirection(worldDirection), 3.55);
    activeBook.targetPosition.y -= 0.05;
    activeBook.targetQuaternion = camera.quaternion.clone().multiply(
      new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), -Math.PI / 2),
    );
    activeBook.fromPosition = startingPosition;
    activeBook.fromQuaternion = startingQuaternion;
    activeBook.fromScale = startingScale;
    activeBook.elapsed = 0;
    activeBook.duration = motionDuration;
    activeBook.mesh.visible = true;
    cameraMove = null;
    controls.enabled = false;
    controls.target.copy(activeBook.targetPosition);
    updateBookPanel(book);
    bookPanel.hidden = false;
    pageControls.hidden = true;
    document.querySelector("#world-interaction-tip").textContent = "LE LIVRE EST ENTRE VOS MAINS · APPUYEZ SUR ÉCHAP POUR LE REPOSER";
  }

  function updateBookPanel(book) {
    document.querySelector("#world-book-title").textContent = book.title;
    document.querySelector("#world-book-author").textContent = book.author;
    document.querySelector("#world-book-series").textContent = book.series || "Récit indépendant";
    document.querySelector("#world-book-category").textContent = book.category_label || "Fantasy";
    document.querySelector("#world-book-year").textContent = book.year || "Non renseignée";
    const availability = book.available === null
      ? "Consulter votre bibliothèque"
      : book.available > 0
        ? `${book.available} exemplaire${book.available === 1 ? "" : "s"} disponible${book.available === 1 ? "" : "s"}`
        : "Aucun exemplaire disponible";
    document.querySelector("#world-book-availability").textContent = availability;
    document.querySelector("#world-book-detail").href = book.detail;
    readingButton.textContent = "OUVRIR LE LIVRE ↗";
  }

  function closeSelectedBook() {
    if (!activeBook) {
      hideReader();
      return;
    }
    hideReader();
    const selected = activeBook;
    activeBook = null;
    bookPanel.hidden = true;
    selected.root.scale.copy(selected.root.userData.originalScale);
    selected.originalParent.add(selected.root);
    selected.root.position.copy(selected.originalPosition);
    selected.root.quaternion.copy(selected.originalRotation);
    selected.root.scale.copy(selected.originalScale);
    controls.enabled = true;
    controls.target.copy(selected.shelf.position);
    cameraMoveTo(camera.position, selected.shelf.position.clone().setY(2.15));
    document.querySelector("#world-interaction-tip").textContent = "CHOISISSEZ UN AUTRE LIVRE OU EXPLOREZ UN NOUVEAU RAYON";
  }

  function toggleReading() {
    if (!activeBook) return;
    if (readerModel) {
      hideReader();
      return;
    }
    showReader(activeBook);
  }

  function showReader(selection) {
    const book = selection.book;
    const root = selection.root;
    readerModel = {
      book,
      cover: null,
      pagePivot: null,
      pageNumber: 1,
      turning: false,
      frontTexture: null,
      backTexture: null,
    };

    const pagesTexture = pageTexture(book, 1);
    const pageMaterial = new THREE.MeshStandardMaterial({
      map: pagesTexture,
      roughness: 0.98,
      side: THREE.DoubleSide,
    });
    const spread = new THREE.Mesh(
      new THREE.PlaneGeometry(0.43, 0.55),
      pageMaterial,
    );
    spread.name = "Pages de lecture originales";
    spread.position.set(0.104, 0, 0.018);
    spread.rotation.y = Math.PI / 2;
    spread.visible = false;
    root.add(spread);
    readerModel.spread = spread;
    readerModel.pageTexture = pagesTexture;

    const coverMaterial = new THREE.MeshStandardMaterial({
      map: coverTexture(book),
      color: 0xf5ebd5,
      roughness: 0.68,
      metalness: 0.04,
    });
    const insideMaterial = new THREE.MeshStandardMaterial({
      map: pageTexture(book, 1, true),
      color: 0xf0e3c9,
      roughness: 0.92,
    });
    const coverMesh = new THREE.Mesh(
      new THREE.BoxGeometry(0.025, 0.63, 0.445),
      [
        new THREE.MeshStandardMaterial({ color: 0x664029, roughness: 0.83 }),
        new THREE.MeshStandardMaterial({ color: 0x664029, roughness: 0.83 }),
        new THREE.MeshStandardMaterial({ color: 0xe5d4b4, roughness: 0.96 }),
        new THREE.MeshStandardMaterial({ color: 0xe5d4b4, roughness: 0.96 }),
        coverMaterial,
        insideMaterial,
      ],
    );
    coverMesh.name = "Couverture ouvrante";
    coverMesh.castShadow = true;
    const hinge = new THREE.Group();
    hinge.name = "Charnière du livre";
    hinge.position.set(0.09, 0, 0.224);
    coverMesh.position.set(0.012, 0, -0.22);
    hinge.add(coverMesh);
    root.add(hinge);
    readerModel.cover = hinge;
    readerModel.coverMesh = coverMesh;
    readerModel.open = false;

    const turnMaterial = new THREE.MeshStandardMaterial({
      map: pageTexture(book, 2),
      roughness: 0.98,
      side: THREE.DoubleSide,
    });
    const pagePivot = new THREE.Group();
    pagePivot.name = "Page qui tourne";
    pagePivot.position.set(0.109, 0, 0.018);
    const turningPage = new THREE.Mesh(new THREE.PlaneGeometry(0.43, 0.55), turnMaterial);
    turningPage.rotation.y = Math.PI / 2;
    turningPage.position.z = -0.215;
    pagePivot.add(turningPage);
    pagePivot.visible = false;
    root.add(pagePivot);
    readerModel.pagePivot = pagePivot;

    selection.mesh.visible = false;
    readerModel.open = true;
    readerModel.spread.visible = true;
    animateCoverOpen(hinge);
    readingButton.textContent = "FERMER LE LIVRE ×";
    pageControls.hidden = false;
  }

  function animateCoverOpen(hinge) {
    const start = performance.now();
    const duration = reducedMotion ? 120 : 720;
    const animateCover = (now) => {
      if (!readerModel || readerModel.cover !== hinge) return;
      const progress = Math.min(1, (now - start) / duration);
      hinge.rotation.y = Math.PI * (1 - (1 - progress) ** 3);
      if (progress < 1) readerTimer = requestAnimationFrame(animateCover);
      else readerTimer = null;
    };
    readerTimer = requestAnimationFrame(animateCover);
  }

  function hideReader() {
    if (readerTimer) {
      cancelAnimationFrame(readerTimer);
      readerTimer = null;
    }
    if (!readerModel || !activeBook) {
      readerModel = null;
      pageControls.hidden = true;
      return;
    }
    for (const child of [
      readerModel.spread,
      readerModel.cover,
      readerModel.pagePivot,
    ]) {
      if (child) activeBook.root.remove(child);
    }
    readerModel.pageTexture?.dispose();
    readerModel.coverMesh?.material?.forEach?.((material, index) => {
      if (index !== 4) material.map?.dispose();
    });
    activeBook.mesh.visible = true;
    readerModel = null;
    pageControls.hidden = true;
    readingButton.textContent = "OUVRIR LE LIVRE ↗";
  }

  function turnPage(direction) {
    if (!readerModel || !readerModel.open || readerModel.turning) return;
    const nextPage = Math.max(1, Math.min(6, readerModel.pageNumber + direction));
    if (nextPage === readerModel.pageNumber) return;
    readerModel.turning = true;
    readerModel.pagePivot.visible = true;
    readerModel.pagePivot.rotation.y = direction > 0 ? 0 : Math.PI;
    readerModel.pagePivot.children[0].material.map.dispose();
    readerModel.pagePivot.children[0].material.map = pageTexture(readerModel.book, nextPage);
    readerModel.pagePivot.children[0].material.needsUpdate = true;
    const start = performance.now();
    const from = readerModel.pagePivot.rotation.y;
    const to = direction > 0 ? Math.PI : 0;
    const duration = reducedMotion ? 100 : 620;
    const animateTurn = (now) => {
      if (!readerModel) return;
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - progress) ** 3;
      readerModel.pagePivot.rotation.y = from + (to - from) * eased;
      if (progress < 1) {
        readerTimer = requestAnimationFrame(animateTurn);
        return;
      }
      readerModel.pageNumber = nextPage;
      readerModel.turning = false;
      readerModel.pagePivot.visible = false;
      readerModel.spread.material.map.dispose();
      readerModel.spread.material.map = pageTexture(readerModel.book, nextPage);
      readerModel.spread.material.needsUpdate = true;
      document.querySelector("#world-page-current").textContent = String(nextPage).padStart(2, "0");
      readerTimer = null;
    };
    readerTimer = requestAnimationFrame(animateTurn);
  }

  function onKeyDown(event) {
    if (event.key === "Escape") {
      closeSelectedBook();
      return;
    }
    if (!readerModel || !readerModel.open) return;
    if (event.key === "ArrowRight") turnPage(1);
    if (event.key === "ArrowLeft") turnPage(-1);
  }

  function onContextLost(event) {
    event.preventDefault();
    console.error("The WebGL context for the interactive library was lost.");
    showFallback();
  }

  function animate() {
    if (!renderer || !scene || !camera) return;
    const delta = Math.min(clock.getDelta(), 0.05);
    const elapsed = clock.elapsedTime;
    const dust = scene.userData.dust;
    if (dust && !reducedMotion) {
      dust.rotation.y = Math.sin(elapsed * 0.09) * 0.025;
      dust.position.y = Math.sin(elapsed * 0.19) * 0.045;
    }

    if (cameraMove) {
      cameraMove.elapsed += delta * 1000;
      const progress = Math.min(1, cameraMove.elapsed / cameraMove.duration);
      const eased = progress * progress * (3 - 2 * progress);
      camera.position.lerpVectors(cameraMove.startPosition, cameraMove.endPosition, eased);
      controls.target.lerpVectors(cameraMove.startTarget, cameraMove.endTarget, eased);
      if (progress >= 1) {
        cameraMove = null;
        controls.enabled = true;
      }
    }

    if (activeBook) {
      activeBook.elapsed += delta * 1000;
      const progress = Math.min(1, activeBook.elapsed / activeBook.duration);
      const eased = progress * progress * (3 - 2 * progress);
      activeBook.root.position.lerpVectors(activeBook.fromPosition, activeBook.targetPosition, eased);
      activeBook.root.quaternion.copy(activeBook.fromQuaternion).slerp(activeBook.targetQuaternion, eased);
      const targetScale = activeBook.fromScale.clone().multiplyScalar(1.65);
      activeBook.root.scale.lerpVectors(activeBook.fromScale, targetScale, eased);
      if (progress >= 1) {
        controls.enabled = true;
        controls.target.copy(activeBook.targetPosition);
      }
    }

    for (const shelf of shelves) {
      const next = shelf.opacity + (shelf.targetOpacity - shelf.opacity) * Math.min(1, delta * 4.5);
      if (Math.abs(next - shelf.opacity) > 0.015) {
        shelf.opacity = next;
        const isDim = shelf.opacity < 0.96;
        shelf.root.traverse((object) => {
          if (!object.isMesh || object === scene.userData.dust) return;
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          for (const material of materials) {
            material.transparent = isDim;
            material.opacity = isDim ? Math.max(0.18, shelf.opacity) : 1;
            material.depthWrite = !isDim;
          }
        });
      }
    }

    for (const mesh of clickableBooks) {
      if (activeBook?.mesh === mesh) continue;
      const bookRoot = mesh.userData.bookRoot;
      if (!bookRoot) continue;
      const destination = bookRoot.userData.originalPosition.z + (bookRoot.userData.hovered ? 0.1 : 0);
      bookRoot.position.z += (destination - bookRoot.position.z) * Math.min(1, delta * 11);
    }

    if (!cameraMove && controls.enabled && !activeBook) controls.update();
    renderer.render(scene, camera);
  }

  function resize() {
    if (!renderer || !camera) return;
    const bounds = canvas.parentElement.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    camera.aspect = bounds.width / bounds.height;
    camera.fov = window.innerWidth < 640 ? 48 : 42;
    camera.updateProjectionMatrix();
    renderer.setSize(bounds.width, bounds.height, false);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, window.innerWidth < 640 ? 1.2 : 1.6));
  }

  function dispose() {
    if (resizeObserver) resizeObserver.disconnect();
    renderer?.setAnimationLoop(null);
    controls?.dispose();
    renderer?.dispose();
    for (const texture of coverTextures.values()) texture.dispose();
  }

  init();
})();
