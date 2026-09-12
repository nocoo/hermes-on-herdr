import { useThree } from "@react-three/fiber";
import { ThreeCanvas } from "@remotion/three";
import { useEffect, useLayoutEffect, useMemo } from "react";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { mix, sceneAt, smooth, timing } from "../timeline";
import { palette as p, type Textures } from "./textures";

type V3 = [number, number, number];

function Box({
  size,
  position = [0, 0, 0],
  rotation = [0, 0, 0],
  color = p.slate,
  metal = 0.55,
}: {
  size: V3;
  position?: V3;
  rotation?: V3;
  color?: string;
  metal?: number;
}) {
  const [width, height, depth] = size;
  const geometry = useMemo(
    () => new RoundedBoxGeometry(width, height, depth, 3, Math.min(0.13, depth / 2)),
    [width, height, depth],
  );
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <mesh geometry={geometry} position={position} rotation={rotation}>
      <meshStandardMaterial color={color} metalness={metal} roughness={0.28} />
    </mesh>
  );
}

function Ring({
  radius,
  position = [0, 0, 0],
  rotation = [0, 0, 0],
  color = p.mint,
  opacity = 0.6,
  thickness = 0.018,
}: {
  radius: number;
  position?: V3;
  rotation?: V3;
  color?: string;
  opacity?: number;
  thickness?: number;
}) {
  return (
    <mesh position={position} rotation={rotation}>
      <torusGeometry args={[radius, thickness, 8, 100]} />
      <meshBasicMaterial
        color={color}
        transparent
        opacity={opacity}
        toneMapped={false}
        depthWrite={false}
      />
    </mesh>
  );
}

function Glow({
  position,
  color = p.mint,
  size = 0.085,
}: {
  position: V3;
  color?: string;
  size?: number;
}) {
  return (
    <group position={position}>
      <mesh>
        <sphereGeometry args={[size, 18, 14]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      <mesh>
        <sphereGeometry args={[size * 2.7, 18, 14]} />
        <meshBasicMaterial color={color} transparent opacity={0.1} depthWrite={false} />
      </mesh>
      <mesh>
        <sphereGeometry args={[size * 5, 16, 12]} />
        <meshBasicMaterial color={color} transparent opacity={0.025} depthWrite={false} />
      </mesh>
    </group>
  );
}

function Route({
  from,
  to,
  color = p.mint,
  opacity = 0.6,
}: {
  from: V3;
  to: V3;
  color?: string;
  opacity?: number;
}) {
  const [ax, ay, az] = from;
  const [bx, by, bz] = to;
  const geometry = useMemo(() => {
    const points = [
      [ax, ay, az],
      [ax, mix(ay, by, 0.5), az],
      [bx, mix(ay, by, 0.5), bz],
      [bx, by, bz],
    ];
    return new THREE.TubeGeometry(
      new THREE.CubicBezierCurve3(
        ...(points.map((point) => new THREE.Vector3(...point)) as [
          THREE.Vector3,
          THREE.Vector3,
          THREE.Vector3,
          THREE.Vector3,
        ]),
      ),
      36,
      0.018,
      6,
      false,
    );
  }, [ax, ay, az, bx, by, bz]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <mesh geometry={geometry}>
      <meshBasicMaterial color={color} transparent opacity={opacity} toneMapped={false} />
    </mesh>
  );
}

function Panel({
  texture,
  width = 5,
  height = 3,
  position = [0, 0, 0],
  rotation = [0, 0, 0],
  accent = p.brass,
}: {
  texture: THREE.Texture;
  width?: number;
  height?: number;
  position?: V3;
  rotation?: V3;
  accent?: string;
}) {
  return (
    <group position={position} rotation={rotation}>
      <Box size={[width + 0.18, height + 0.18, 0.2]} color="#718383" />
      <mesh position={[0, 0, 0.112]}>
        <planeGeometry args={[width, height]} />
        <meshBasicMaterial map={texture} toneMapped={false} />
      </mesh>
      <mesh position={[-width / 2 - 0.035, 0, 0.06]}>
        <boxGeometry args={[0.022, height - 0.3, 0.1]} />
        <meshBasicMaterial color={accent} toneMapped={false} />
      </mesh>
      {[-1, 1].flatMap((x) =>
        [-1, 1].map((y) => (
          <mesh
            key={`${x}/${y}`}
            position={[x * (width / 2 + 0.016), y * (height / 2 + 0.016), 0.119]}
          >
            <sphereGeometry args={[0.022, 8, 6]} />
            <meshStandardMaterial color={p.brass} metalness={0.85} roughness={0.2} />
          </mesh>
        )),
      )}
    </group>
  );
}

function Label({
  texture,
  width = 3,
  position = [0, 0, 0.22],
}: {
  texture: THREE.Texture;
  width?: number;
  position?: V3;
}) {
  return (
    <mesh position={position}>
      <planeGeometry args={[width, width / 3]} />
      <meshBasicMaterial map={texture} transparent toneMapped={false} depthWrite={false} />
    </mesh>
  );
}

function Node({
  position,
  texture,
  radius = 1,
  color = p.mint,
}: {
  position: V3;
  texture: THREE.Texture;
  radius?: number;
  color?: string;
}) {
  return (
    <group position={position}>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[radius, radius, 0.22, 64]} />
        <meshStandardMaterial color="#19353d" metalness={0.62} roughness={0.28} />
      </mesh>
      <Ring
        radius={radius + 0.025}
        position={[0, 0, 0.12]}
        color={color}
        opacity={0.8}
        thickness={0.023}
      />
      <Ring radius={radius + 0.15} position={[0, 0, -0.025]} color={color} opacity={0.15} />
      <Label texture={texture} width={radius * 2.8} />
      <Glow position={[0, radius + 0.05, 0.21]} color={color} size={0.045} />
    </group>
  );
}

function Platform({ frame, warm = false }: { frame: number; warm?: boolean }) {
  return (
    <group position={[0, -3.25, -0.4]}>
      <mesh>
        <cylinderGeometry args={[4.2, 4.3, 0.28, 100]} />
        <meshStandardMaterial
          color={warm ? "#496265" : "#17313a"}
          metalness={0.62}
          roughness={0.4}
        />
      </mesh>
      <Ring
        radius={4.18}
        rotation={[Math.PI / 2, 0, 0]}
        position={[0, 0.16, 0]}
        color={p.brass}
        opacity={0.7}
      />
      <Ring radius={3.8} rotation={[Math.PI / 2, 0, 0]} position={[0, 0.17, 0]} opacity={0.22} />
      <Ring radius={4.8} rotation={[Math.PI / 2, 0, 0]} position={[0, -0.16, 0]} opacity={0.12} />
      {Array.from({ length: 32 }, (_, i) => {
        const angle = (i / 32) * Math.PI * 2;
        return (
          <mesh
            key={angle}
            position={[Math.sin(angle) * 4.01, 0.172, Math.cos(angle) * 4.01]}
            rotation={[0, angle, 0]}
          >
            <boxGeometry args={[0.024, 0.014, i % 4 === 0 ? 0.18 : 0.09]} />
            <meshBasicMaterial color={p.brass} transparent opacity={0.45} />
          </mesh>
        );
      })}
      <Glow position={[Math.sin(frame / 78) * 3.8, 0.26, Math.cos(frame / 78) * 3.8]} size={0.1} />
    </group>
  );
}

function Door({ frame, scale = 1 }: { frame: number; scale?: number }) {
  return (
    <group
      scale={scale}
      position={[0, Math.sin(frame / 62) * 0.035, 0]}
      rotation={[0, -0.15 + Math.sin(frame / 150) * 0.045, 0]}
    >
      <Box size={[3.65, 0.55, 0.48]} position={[0, 2.35, 0]} color={p.brass} metal={0.82} />
      <Box size={[0.52, 4.6, 0.48]} position={[-1.56, -0.08, 0]} color={p.brass} metal={0.82} />
      <Box size={[0.52, 4.6, 0.48]} position={[1.56, -0.08, 0]} color={p.brass} metal={0.82} />
      <Box size={[3.6, 0.35, 0.48]} position={[0, -2.35, 0]} color={p.brass} metal={0.82} />
      <group position={[-1.27, 0, 0.02]} rotation={[0, -0.52 + Math.sin(frame / 100) * 0.055, 0]}>
        <Box size={[2.53, 4.16, 0.25]} position={[1.22, -0.02, 0]} color="#245166" metal={0.58} />
        <Box
          size={[0.66, 0.13, 0.03]}
          position={[1.15, 0.13, 0.16]}
          rotation={[0, 0, -0.57]}
          color="#ece4c9"
          metal={0.2}
        />
        <Box
          size={[0.66, 0.13, 0.03]}
          position={[1.15, -0.22, 0.16]}
          rotation={[0, 0, 0.57]}
          color="#ece4c9"
          metal={0.2}
        />
        <Box size={[0.54, 0.13, 0.03]} position={[1.86, -0.42, 0.16]} color="#ece4c9" metal={0.2} />
      </group>
      {[-1.2, 1.2].map((y) => (
        <mesh key={y} position={[-1.32, y, 0.28]}>
          <cylinderGeometry args={[0.105, 0.105, 0.56, 24]} />
          <meshStandardMaterial color={p.brass} metalness={0.84} roughness={0.2} />
        </mesh>
      ))}
      <Ring
        radius={0.13}
        position={[1.12, 2.35, 0.27]}
        color="#eadcb0"
        opacity={1}
        thickness={0.028}
      />
      <Glow position={[1.12, 2.35, 0.295]} size={0.105} />
    </group>
  );
}

function Stage({ index, frame, textures }: { index: number; frame: number; textures: Textures }) {
  const shot = timing.scenes[index];
  const local = frame - shot.start;
  const messageEntry = smooth((local - shot.duration * 0.42) / 36);
  const float = Math.sin(frame / 70) * 0.07;
  const phase = Math.min(4, Math.floor((local / shot.duration) * 5));
  const status = phase === 4 ? "stopped" : phase === 1 || phase === 2 ? "paused" : "ready";
  const statusColor = status === "ready" ? p.mint : status === "paused" ? p.amber : p.muted;
  const agents: V3[] = [
    [-2.1, 1.48, -0.1],
    [2.02, 1.28, -0.65],
    [-2.13, -1.25, 0.8],
    [2.1, -1.35, 0.15],
  ];
  return (
    <group>
      <Platform frame={frame} warm={index === 9} />
      {index === 0 && (
        <>
          <Door frame={frame} scale={1.04} />
          <Ring radius={3.52} rotation={[0.08, 0.44, -0.35]} opacity={0.28} />
          <Ring radius={3.75} rotation={[-0.5, -0.45, 0.25]} color={p.brass} opacity={0.22} />
          <Glow
            position={[Math.sin(frame / 68) * 3.53, Math.cos(frame / 68) * 3.45, 0.5]}
            size={0.12}
          />
        </>
      )}
      {(index === 1 || index === 2) && (
        <>
          <Ring radius={3.6} rotation={[0.3, 0.24, frame / 550]} opacity={0.26} />
          {agents.map((position, i) => {
            const entry = smooth((local - i * 9) / 25);
            const stress = index === 2 ? Math.sin(frame / 30 + i) * 0.18 : 0;
            return (
              <group
                key={textures[`agent${i}`].uuid}
                position={[
                  position[0],
                  position[1] + float + stress,
                  position[2] + (1 - entry) * -2,
                ]}
                scale={0.9 + entry * 0.1}
              >
                <Panel
                  texture={textures[`agent${i}`]}
                  width={3.92}
                  height={2.35}
                  rotation={[0.025, position[0] > 0 ? -0.1 : 0.1, stress * 0.06]}
                  accent={index === 2 && i % 2 ? p.amber : p.mint}
                />
                {index === 2 && (
                  <Label
                    texture={textures[i === 1 ? "blocked" : i === 3 ? "done" : "working"]}
                    width={2.7}
                    position={[0, -0.77, 0.3]}
                  />
                )}
              </group>
            );
          })}
          <Glow position={[0, float, 2]} size={0.16} />
          {agents.map((position, i) => (
            <Route
              key={position[0] + position[1]}
              from={[0, 0, 1.3]}
              to={position}
              color={index === 2 && i === 1 ? p.amber : p.mint}
              opacity={0.22}
            />
          ))}
        </>
      )}
      {index === 3 && (
        <>
          <Node position={[0, 1.2, 0]} radius={1.28} texture={textures.herdr} color={p.brass} />
          {[-3.05, -1.02, 1.02, 3.05].map((x, i) => (
            <group key={x}>
              <Route from={[0, 0.2, 0]} to={[x, -1.95, 0.9]} />
              <Node
                position={[x, -1.95, 0.9]}
                radius={0.64}
                texture={textures[`agent-label${i}`]}
              />
              <Glow
                position={[
                  mix(0, x, (frame % 120) / 120),
                  mix(0.2, -1.95, (frame % 120) / 120),
                  0.95,
                ]}
                size={0.055}
              />
            </group>
          ))}
          <Ring radius={2.02} position={[0, 1.2, -0.28]} rotation={[0, 0.42, 0]} opacity={0.18} />
        </>
      )}
      {index === 4 && (
        <>
          <Panel
            texture={textures.clock}
            width={6.05}
            height={3.63}
            position={[0, 0.4, 0.25]}
            rotation={[0.01, -0.1, 0]}
          />
          <Box size={[0.36, 1.25, 0.44]} position={[0, -2.05, -0.35]} color="#566867" />
          <Box size={[2.65, 0.18, 1.35]} position={[0, -2.73, 0.1]} color="#566867" />
          <Ring
            radius={3.63}
            position={[0, 0.3, -0.4]}
            color={p.brass}
            opacity={0.5}
            thickness={0.025}
          />
          <Glow
            position={[
              Math.sin(local / 150 + 0.5) * 3.63,
              0.3 + Math.cos(local / 150 + 0.5) * 3.63,
              -0.3,
            ]}
            color={p.amber}
            size={0.22}
          />
        </>
      )}
      {index === 5 && (
        <>
          <Label texture={textures.you} width={2.4} position={[0, 4.14, 0]} />
          <Route from={[0, 3.6, 0]} to={[0, 2.8, 0]} color={p.brass} />
          <Node position={[0, 2.25, 0]} radius={1.12} texture={textures.hermes} color={p.brass} />
          <Route from={[0, 1.2, 0.1]} to={[0, -0.16, 0.5]} color={p.brass} />
          <Node position={[0, -0.28, 0.6]} radius={0.86} texture={textures.herdr} />
          {[-3.0, -1, 1, 3.0].map((x, i) => (
            <group key={x}>
              <Route from={[0, -1.05, 0.5]} to={[x, -2.05, 1.8]} />
              <Node position={[x, -2.05, 1.8]} radius={0.6} texture={textures[`agent-label${i}`]} />
            </group>
          ))}
          <Ring
            radius={1.48}
            position={[0, 2.25, -0.4]}
            rotation={[0, 0.3, 0.2]}
            color={p.brass}
            opacity={0.25}
          />
          <Glow position={[0, mix(3.4, -1, (frame % 135) / 135), 0.9]} size={0.08} />
        </>
      )}
      {index === 6 && (
        <>
          <Panel
            texture={textures.control}
            width={7.45}
            height={4.47}
            position={[0, 0.2 + float, 0.2]}
            rotation={[0.04, 0.1, -0.015]}
          />
          <Ring
            radius={3.5}
            position={[0, 0.25, -0.4]}
            rotation={[0, -0.32, 0.2]}
            color={p.brass}
            opacity={0.5}
            thickness={0.03}
          />
          <Ring
            radius={4.0}
            position={[0, 0.25, -0.5]}
            rotation={[0, -0.4, -0.15]}
            color={p.brass}
            opacity={0.13}
          />
          <Glow
            position={[Math.cos(frame / 68) * 3.7, 0.25 + Math.sin(frame / 68) * 3.2, 0.55]}
            color={p.brass}
            size={0.1}
          />
        </>
      )}
      {index === 7 && (
        <>
          <Node
            position={[-2.0, 1.65, 0]}
            radius={1.03}
            texture={textures.herdr}
            color={statusColor}
          />
          <Node
            position={[2.0, 1.65, 0]}
            radius={1.03}
            texture={textures.hermes}
            color={statusColor}
          />
          <Route from={[-0.9, 1.65, 0]} to={[0.9, 1.65, 0]} color={statusColor} />
          <Ring radius={1.4} position={[-2, 1.65, -0.3]} color={statusColor} opacity={0.25} />
          <Ring radius={1.4} position={[2, 1.65, -0.3]} color={statusColor} opacity={0.25} />
          <Label texture={textures[status]} width={3.0} position={[0, -0.3, 0.4]} />
          <Panel
            texture={textures.lifecycle}
            width={5.85}
            height={3.51}
            position={[0, -1.6, -0.4]}
            rotation={[-0.04, 0, 0]}
          />
        </>
      )}
      {index === 8 && (
        <>
          <Panel
            texture={textures.monitor}
            width={8.1}
            height={(8.1 * 828) / 1476}
            position={[-0.12, 0.72 + float, -0.2]}
            rotation={[0.04, -0.065, 0]}
          />
          {messageEntry > 0 && (
            <group position={[0, (1 - messageEntry) * -1.5, 0]} scale={0.85 + messageEntry * 0.15}>
              <Panel
                texture={textures.message}
                width={4.75}
                height={4.75 * 0.65}
                position={[1.5, -1.5 + float, 1.8]}
                rotation={[-0.025, -0.1, 0]}
                accent={p.mint}
              />
            </group>
          )}
          <Ring
            radius={3.85}
            position={[0, -0.25, -0.9]}
            rotation={[0.2, -0.34, 0]}
            opacity={0.22}
          />
          <Glow
            position={[
              -3.9 + smooth((local % 140) / 140) * 6.5,
              -0.8 + Math.sin(local / 30) * 0.3,
              2.3,
            ]}
            size={0.085}
          />
        </>
      )}
      {index === 9 && (
        <>
          <Door frame={frame} scale={0.95} />
          <Ring radius={3.54} rotation={[0.06, 0.34, -0.24]} color={p.brass} opacity={0.37} />
          <Ring radius={3.84} rotation={[-0.4, -0.5, 0.25]} opacity={0.19} />
          <Glow
            position={[Math.sin(frame / 68) * 3.53, Math.cos(frame / 68) * 3.4, 0.5]}
            size={0.11}
          />
        </>
      )}
    </group>
  );
}

function Camera({ frame }: { frame: number }) {
  const { camera } = useThree();
  const shot = sceneAt(frame);
  const settle = smooth(shot.local / 55);
  useLayoutEffect(() => {
    camera.position.set(0.7 + Math.sin(frame / 310) * 0.16, 3.1, 21.3 + (1 - settle) * 0.9);
    camera.lookAt(0, -0.1, 0);
    (camera as THREE.PerspectiveCamera).setViewOffset(
      1920,
      1080,
      960 - shot.center,
      -3,
      1920,
      1080,
    );
    camera.updateProjectionMatrix();
  }, [camera, frame, settle, shot.center]);
  return null;
}

export function World({ frame, textures }: { frame: number; textures: Textures }) {
  const shot = sceneAt(frame);
  // One full-size canvas prevents moving-stage clipping. Every motion uses frame.
  return (
    <ThreeCanvas
      width={1920}
      height={1080}
      dpr={1}
      camera={{ position: [0.7, 3.1, 21.3], fov: 35, near: 0.1, far: 100 }}
      gl={{
        alpha: true,
        antialias: true,
        powerPreference: "high-performance",
        toneMapping: THREE.ACESFilmicToneMapping,
        toneMappingExposure: 1.25,
      }}
      onCreated={({ gl }) => gl.setClearColor(0, 0)}
      style={{
        position: "absolute",
        inset: 0,
        width: 1920,
        height: 1080,
        background: "transparent",
      }}
    >
      <Camera frame={frame} />
      <ambientLight intensity={1.4} />
      <hemisphereLight args={["#e9f4eb", "#182c35", 2]} />
      <directionalLight position={[-4, 8, 6]} color="#fff3d5" intensity={5.8} />
      <directionalLight position={[6, 2, 3]} color="#b0e4e7" intensity={3.4} />
      <directionalLight position={[1, 5, -4]} color="#bd9a5d" intensity={4.5} />
      <group position={[0, (1 - shot.entry) * -0.25, 0]} scale={0.96 + shot.entry * 0.04}>
        <Stage index={shot.index} frame={frame} textures={textures} />
      </group>
    </ThreeCanvas>
  );
}
