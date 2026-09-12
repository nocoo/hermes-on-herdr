import { hexly } from "@hexly/video-kit";
import { ContactShadows } from "@react-three/drei";
import { useLoader, useThree } from "@react-three/fiber";
import { DepthOfField, EffectComposer } from "@react-three/postprocessing";
import { ThreeCanvas } from "@remotion/three";
import { useLayoutEffect, useMemo } from "react";
import { staticFile } from "remotion";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { between, lerp } from "../timeline";
import { type CubieSpec, candy, sceneCubies, type Vec3 } from "./cube";

const body = new RoundedBoxGeometry(1, 1, 1, 5, 0.105);
const sticker = new RoundedBoxGeometry(0.83, 0.83, 0.018, 3, 0.055);
const plate = new RoundedBoxGeometry(1, 1, 0.1, 4, 0.055);

function canvasTexture(width: number, height: number, draw: (c: CanvasRenderingContext2D) => void) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const c = canvas.getContext("2d");
  if (!c) throw new Error("Canvas textures require a 2D context");
  draw(c);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}

const labels = new Map<string, THREE.Texture>();
function labelTexture(label: string, detail: string) {
  const key = `${label}/${detail}`;
  const cached = labels.get(key);
  if (cached) return cached;
  const texture = canvasTexture(512, 512, (c) => {
    c.textAlign = "center";
    c.fillStyle = hexly.ink;
    let size = 86;
    do {
      c.font = `600 ${size}px "Space Grotesk Variable"`;
      if (c.measureText(label).width <= 450) break;
      size -= 2;
    } while (size > 36);
    c.fillText(label, 256, detail ? 269 : 285);
    if (detail) {
      c.font = '29px "Geist Mono Variable"';
      c.fillText(detail, 256, 376, 438);
    }
    c.strokeStyle = `${hexly.ink}25`;
    c.lineWidth = 2;
    c.beginPath();
    c.moveTo(205, 116);
    c.lineTo(307, 116);
    c.stroke();
  });
  labels.set(key, texture);
  return texture;
}

function Cubie({ spec }: { spec: CubieSpec }) {
  const face = labelTexture(spec.label, spec.detail);
  return (
    <group position={spec.position} rotation={spec.rotation} scale={spec.scale}>
      <mesh geometry={body} castShadow receiveShadow>
        <meshPhysicalMaterial
          color={spec.color}
          roughness={0.3}
          metalness={0.02}
          clearcoat={0.3}
          clearcoatRoughness={0.3}
          envMapIntensity={0.22}
        />
      </mesh>
      <mesh geometry={sticker} position={[0, 0, 0.499]} receiveShadow>
        <meshPhysicalMaterial
          color={spec.color}
          roughness={0.46}
          clearcoat={0.18}
          envMapIntensity={0.12}
        />
      </mesh>
      <mesh position={[0, 0, 0.512]}>
        <planeGeometry args={[0.81, 0.81]} />
        <meshBasicMaterial map={face} transparent toneMapped={false} depthWrite={false} />
      </mesh>
    </group>
  );
}

function Rail({
  from,
  to,
  color = "#bec9b5",
  width = 0.038,
}: {
  from: Vec3;
  to: Vec3;
  color?: string;
  width?: number;
}) {
  const a = new THREE.Vector3(...from);
  const b = new THREE.Vector3(...to);
  const mid = a.clone().add(b).multiplyScalar(0.5);
  const direction = b.clone().sub(a);
  const quaternion = new THREE.Quaternion().setFromUnitVectors(
    new THREE.Vector3(0, 1, 0),
    direction.clone().normalize(),
  );
  return (
    <mesh position={mid} quaternion={quaternion} receiveShadow>
      <boxGeometry args={[width, direction.length(), width]} />
      <meshPhysicalMaterial color={color} roughness={0.55} />
    </mesh>
  );
}

function SessionTray({ position, size }: { position: Vec3; size: [number, number] }) {
  return (
    <group position={position}>
      <mesh geometry={plate} scale={[size[0], 0.15, size[1] * 9.0]} receiveShadow castShadow>
        <meshPhysicalMaterial color={hexly.soft} roughness={0.62} />
      </mesh>
      <Rail
        from={[-size[0] / 2, 0.09, size[1] / 2]}
        to={[size[0] / 2, 0.09, size[1] / 2]}
        color={hexly.accent}
        width={0.026}
      />
    </group>
  );
}

function MessagePhone() {
  const texture = useMemo(
    () =>
      canvasTexture(640, 1040, (c) => {
        c.fillStyle = hexly.surface;
        c.fillRect(0, 0, 640, 1040);
        c.fillStyle = hexly.muted;
        c.font = '26px "Geist Mono Variable"';
        c.fillText("YOUR CHANNEL", 62, 105);
        c.fillStyle = hexly.ink;
        c.font = '500 52px "Space Grotesk Variable"';
        c.fillText("To: Hermes", 62, 205);
        c.fillStyle = candy.peach;
        c.beginPath();
        c.roundRect(40, 345, 560, 265, 26);
        c.fill();
        c.fillStyle = hexly.ink;
        c.font = '500 42px "Space Grotesk Variable"';
        c.fillText("Check the team.", 80, 430);
        c.fillText("What's next?", 80, 493);
        c.fillStyle = hexly.muted;
        c.font = '23px "Geist Mono Variable"';
        c.fillText("ILLUSTRATIVE REQUEST", 62, 895);
        c.fillText("NO LIVE MESSAGE SENT", 62, 932);
      }),
    [],
  );
  return (
    <group position={[-2.2, -0.45, 0.55]} rotation={[0, 0.12, -0.035]}>
      <mesh geometry={plate} scale={[1.74, 2.8, 1.4]} castShadow>
        <meshPhysicalMaterial color={hexly.surface} roughness={0.25} clearcoat={0.45} />
      </mesh>
      <mesh position={[0, 0, 0.074]}>
        <planeGeometry args={[1.62, 2.63]} />
        <meshBasicMaterial map={texture} toneMapped={false} />
      </mesh>
    </group>
  );
}

function Monitor({ seconds }: { seconds: number }) {
  const texture = useLoader(THREE.TextureLoader, staticFile("cli/monitor-ready.svg"));
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return (
    <group
      position={[0.1, 0.8, -0.2]}
      rotation={[0.17, lerp(-0.08, 0.02, between(seconds, 0, 5)), 0]}
    >
      <mesh geometry={plate} scale={[8.04, 5.1, 2.4]} castShadow receiveShadow>
        <meshPhysicalMaterial color={hexly.surface} roughness={0.3} clearcoat={0.35} />
      </mesh>
      <mesh position={[0, 0, 0.126]}>
        <planeGeometry args={[7.84, 4.9]} />
        <meshBasicMaterial map={texture} toneMapped={false} />
      </mesh>
    </group>
  );
}

function Environment({ id, seconds }: { id: string; seconds: number }) {
  const { gl, scene, camera } = useThree();
  useLayoutEffect(() => {
    const generator = new THREE.PMREMGenerator(gl);
    const room = new RoomEnvironment();
    const env = generator.fromScene(room, 0.035);
    scene.environment = env.texture;
    scene.environmentIntensity = 0.3;
    return () => {
      scene.environment = null;
      env.dispose();
      room.dispose();
      generator.dispose();
    };
  }, [gl, scene]);
  useLayoutEffect(() => {
    const wide = id === "monitor";
    camera.position.set(
      0.5 + Math.sin(seconds * 0.13) * 0.42,
      wide ? 4.0 : 4.35 + Math.sin(seconds * 0.1) * 0.2,
      wide ? 16.7 : 15.0,
    );
    camera.lookAt(0.1, 0.1, 0);
    camera.updateProjectionMatrix();
  }, [camera, seconds, id]);
  return (
    <>
      <color attach="background" args={[hexly.page]} />
      <ambientLight intensity={0.3} color="#fffaf1" />
      <hemisphereLight args={["#fffdfa", "#c3d2b8", 0.72]} />
      <directionalLight position={[-4, 9, 7]} intensity={1.64} color="#fff7ec" />
      <directionalLight position={[7, 4, -4]} intensity={0.9} color="#eaf3ff" />
      <ContactShadows
        position={[0, -2.78, 0]}
        opacity={0.36}
        scale={19}
        blur={2.5}
        far={7}
        resolution={1024}
        color="#65745a"
        frames={Infinity}
      />
    </>
  );
}

function SetPieces({ id, seconds }: { id: string; seconds: number }) {
  const phase = (seconds * 0.19) % 1;
  const signal = (position: Vec3) => (
    <mesh position={position} geometry={body} scale={0.16} castShadow>
      <meshPhysicalMaterial color={candy.peach} roughness={0.28} clearcoat={0.5} />
    </mesh>
  );
  if (id === "context")
    return (
      <>
        <Rail from={[-1.1, -0.2, 0.5]} to={[-0.58, -0.2, 0.5]} />
        <Rail from={[0.12, -0.2, 0.5]} to={[0.55, -0.2, 0.5]} />
        <SessionTray position={[1.45, -2.25, 0]} size={[3.6, 3.4]} />
      </>
    );
  if (id === "bind") return <SessionTray position={[0.4, -2.05, -0.4]} size={[4.1, 4.1]} />;
  if (id === "managers")
    return (
      <>
        <Rail from={[0, 1.5, -0.15]} to={[0, -1.05, -0.15]} />
        <Rail from={[-2.7, -1.05, -0.15]} to={[2.7, -1.05, -0.15]} />
        {[-2.7, -0.9, 0.9, 2.7].map((x) => (
          <Rail key={x} from={[x, -1.05, -0.15]} to={[x, -1.75, -0.15]} />
        ))}
        {signal([0, lerp(1.35, 0.85, phase), 0.15])}
      </>
    );
  if (id === "channels")
    return (
      <>
        <MessagePhone />
        <Rail from={[-1.3, -0.65, 0.5]} to={[2.5, -0.65, 0.5]} />
        <SessionTray position={[1.55, -1.68, 0.05]} size={[3.45, 2.8]} />
        {signal([lerp(-1.25, -0.27, phase), -0.64, 0.6])}
      </>
    );
  if (id === "local")
    return (
      <>
        <SessionTray position={[0.8, -2.03, -0.2]} size={[4.1, 4.1]} />
        <Rail from={[-1.15, 0.25, 0.5]} to={[0.1, 0.25, 0.5]} />
        {signal([lerp(-1.05, 0.02, phase), 0.25, 0.62])}
      </>
    );
  if (id === "monitor") return <Monitor seconds={seconds} />;
  if (id === "trust")
    return (
      <>
        <SessionTray position={[1.15, -1.6, 0]} size={[3.85, 3.3]} />
        <Rail from={[0.65, 0.25, 0.4]} to={[1.8, -0.25, 0.15]} />
      </>
    );
  return null;
}

function Stage({ id, seconds }: { id: string; seconds: number }) {
  const nodes = sceneCubies(id, seconds).map((node, index) => {
    if (id === "weekend") return node;
    const arrive = between(seconds, Math.min(index * 0.06, 0.5), 1.3 + Math.min(index * 0.06, 0.5));
    return {
      ...node,
      position: [
        node.position[0],
        node.position[1] + (1 - arrive) * 0.42,
        node.position[2] - (1 - arrive) * 1.0,
      ] as Vec3,
      rotation: [
        node.rotation[0],
        node.rotation[1] + (1 - arrive) * (index % 2 ? -0.8 : 0.8),
        node.rotation[2],
      ] as Vec3,
    };
  });
  const center: Vec3 =
    id === "monitor"
      ? [3.2, -0.15, 0]
      : [3.25, id === "weekend" ? lerp(1.0, -0.03, between(seconds, 0.2, 2.6)) : -0.03, 0];
  const scale = id === "weekend" ? 1.38 : id === "managers" ? 1.06 : 1.15;
  const turn: Vec3 =
    id === "weekend"
      ? [-0.03, lerp(-0.7, -0.42, between(seconds, 0, 8)), -0.02]
      : [0, -0.28 + Math.sin(seconds * 0.18) * 0.055, 0];
  return (
    <>
      <Environment id={id} seconds={seconds} />
      <group position={center} scale={scale} rotation={turn}>
        {nodes.map((spec) => (
          <Cubie key={spec.id} spec={spec} />
        ))}
        <SetPieces id={id} seconds={seconds} />
      </group>
      <EffectComposer multisampling={4}>
        <DepthOfField
          worldFocusDistance={id === "monitor" ? 17 : 15.5}
          worldFocusRange={id === "monitor" ? 10 : 6}
          bokehScale={1.25}
          resolutionScale={1}
        />
      </EffectComposer>
    </>
  );
}

export function World({ id, frame }: { id: string; frame: number }) {
  return (
    <ThreeCanvas
      width={1920}
      height={1080}
      dpr={1}
      shadows
      camera={{ fov: 33, near: 0.1, far: 100, position: [0.5, 4.35, 15] }}
      gl={{ alpha: true, antialias: true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.setClearColor(0x000000, 0);
        gl.shadowMap.type = THREE.VSMShadowMap;
        gl.outputColorSpace = THREE.SRGBColorSpace;
      }}
    >
      <Stage id={id} seconds={frame / 30} />
    </ThreeCanvas>
  );
}
