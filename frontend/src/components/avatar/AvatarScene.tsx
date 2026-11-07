import { useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import type { Group, Mesh } from 'three'
import type { AvatarState } from './InterviewerAvatar'

/**
 * A procedurally modelled interviewer (no external model file, so there is no licence question).
 * Mouth movement while speaking is an APPROXIMATE open/close rhythm - it is not phoneme/viseme lip-sync.
 */
function Interviewer({ state }: { state: AvatarState }) {
  const root = useRef<Group>(null)
  const head = useRef<Group>(null)
  const mouth = useRef<Mesh>(null)
  const lids = useRef<Group>(null)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    if (root.current) root.current.position.y = Math.sin(t * 1.4) * 0.012 // breathing
    if (head.current) {
      const speaking = state === 'speaking'
      head.current.rotation.y = speaking ? Math.sin(t * 1.1) * 0.08 : state === 'listening' ? Math.sin(t * 0.5) * 0.04 : 0
      head.current.rotation.x = speaking ? Math.sin(t * 2.3) * 0.03 : state === 'listening' ? 0.05 : 0
      head.current.rotation.z = state === 'listening' ? 0.06 : 0
    }
    if (mouth.current) {
      const open = state === 'speaking' ? 0.25 + 0.75 * Math.abs(Math.sin(t * 9) * Math.sin(t * 5.3 + 1)) : 0.12
      mouth.current.scale.y = open
    }
    if (lids.current) {
      const blink = Math.sin(t * 1.3 + 2) > 0.985 || Math.sin(t * 0.7) > 0.997 // occasional blink
      lids.current.scale.y = blink ? 0.1 : 1
    }
  })

  return (
    <group ref={root}>
      {/* shoulders / torso */}
      <mesh position={[0, -1.25, 0]}>
        <capsuleGeometry args={[0.62, 0.7, 8, 24]} />
        <meshStandardMaterial color="#1f3a5f" roughness={0.7} />
      </mesh>
      <mesh position={[0, -0.78, 0.18]} rotation={[0.2, 0, 0]}>
        <boxGeometry args={[0.28, 0.4, 0.05]} />
        <meshStandardMaterial color="#f4f1ea" roughness={0.8} />
      </mesh>
      {/* neck */}
      <mesh position={[0, -0.62, 0]}>
        <cylinderGeometry args={[0.14, 0.17, 0.3, 20]} />
        <meshStandardMaterial color="#c99a7a" roughness={0.6} />
      </mesh>
      <group ref={head} position={[0, 0.05, 0]}>
        <mesh>
          <sphereGeometry args={[0.52, 40, 40]} />
          <meshStandardMaterial color="#d8a98b" roughness={0.55} />
        </mesh>
        {/* hair */}
        <mesh position={[0, 0.2, -0.06]}>
          <sphereGeometry args={[0.54, 40, 40, 0, Math.PI * 2, 0, Math.PI * 0.52]} />
          <meshStandardMaterial color="#2a1d17" roughness={0.9} />
        </mesh>
        {/* ears */}
        {[-0.52, 0.52].map((x) => (
          <mesh key={x} position={[x, 0, 0]} scale={[0.5, 1, 0.7]}>
            <sphereGeometry args={[0.1, 16, 16]} />
            <meshStandardMaterial color="#d0a083" roughness={0.6} />
          </mesh>
        ))}
        {/* eyes */}
        <group ref={lids}>
          {[-0.19, 0.19].map((x) => (
            <group key={x} position={[x, 0.08, 0.46]}>
              <mesh><sphereGeometry args={[0.07, 20, 20]} /><meshStandardMaterial color="#fbfbf8" /></mesh>
              <mesh position={[0, 0, 0.045]}><sphereGeometry args={[0.035, 16, 16]} /><meshStandardMaterial color="#2b1a10" /></mesh>
            </group>
          ))}
        </group>
        {/* brows */}
        {[-0.19, 0.19].map((x) => (
          <mesh key={x} position={[x, 0.2, 0.47]} rotation={[0, 0, x < 0 ? 0.08 : -0.08]}>
            <boxGeometry args={[0.16, 0.026, 0.03]} />
            <meshStandardMaterial color="#2a1d17" />
          </mesh>
        ))}
        {/* nose */}
        <mesh position={[0, -0.03, 0.51]} scale={[0.8, 1.2, 0.8]}>
          <sphereGeometry args={[0.06, 16, 16]} />
          <meshStandardMaterial color="#cf9f81" roughness={0.6} />
        </mesh>
        {/* mouth */}
        <mesh ref={mouth} position={[0, -0.22, 0.47]} scale={[1, 0.12, 1]}>
          <sphereGeometry args={[0.1, 20, 20]} />
          <meshStandardMaterial color="#6b2a2a" roughness={0.5} />
        </mesh>
      </group>
    </group>
  )
}

export default function AvatarScene({ state }: { state: AvatarState }) {
  return (
    <Canvas camera={{ position: [0, 0, 3.1], fov: 32 }} dpr={[1, 1.5]} frameloop="always" aria-hidden>
      <ambientLight intensity={0.85} />
      <directionalLight position={[2, 3, 4]} intensity={1.6} />
      <directionalLight position={[-3, 1, 2]} intensity={0.5} color="#bcd0ff" />
      <Interviewer state={state} />
    </Canvas>
  )
}
