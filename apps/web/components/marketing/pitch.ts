export const PITCH = { halfLength: 52.5, halfWidth: 34 } as const;

export type PitchPoint = { x: number; z: number; glyph: string; spot: boolean };
export type FieldPoint = { x: number; z: number };

const SAMPLE_STEP_METRES = 0.9;
const FIELD_STEP_X = 3.5;
const FIELD_STEP_Z = 3.4;

/** The markings of a 105 by 68 m pitch, sampled every 0.9 m and printed as digits, plus a sparse grass grid. */
export function buildPitch(): { lines: readonly PitchPoint[]; field: readonly FieldPoint[] } {
  const raw: { x: number; z: number; spot: boolean }[] = [];
  const line = (x1: number, z1: number, x2: number, z2: number) => {
    const steps = Math.max(1, Math.round(Math.hypot(x2 - x1, z2 - z1) / SAMPLE_STEP_METRES));
    for (let i = 0; i <= steps; i++) raw.push({ x: x1 + ((x2 - x1) * i) / steps, z: z1 + ((z2 - z1) * i) / steps, spot: false });
  };
  const arc = (cx: number, cz: number, radius: number, from: number, to: number) => {
    const steps = Math.max(2, Math.round((Math.abs(to - from) * radius) / SAMPLE_STEP_METRES));
    for (let i = 0; i <= steps; i++) {
      const angle = from + ((to - from) * i) / steps;
      raw.push({ x: cx + radius * Math.cos(angle), z: cz + radius * Math.sin(angle), spot: false });
    }
  };

  const { halfLength: L, halfWidth: W } = PITCH;
  line(-L, -W, L, -W);
  line(-L, W, L, W);
  line(-L, -W, -L, W);
  line(L, -W, L, W);
  line(0, -W, 0, W);
  arc(0, 0, 9.15, 0, Math.PI * 2);

  for (const side of [-1, 1]) {
    const goalLine = side * L;
    const boxEdge = side * (L - 16.5);
    const sixYardEdge = side * (L - 5.5);
    line(goalLine, -20.16, boxEdge, -20.16);
    line(goalLine, 20.16, boxEdge, 20.16);
    line(boxEdge, -20.16, boxEdge, 20.16);
    line(goalLine, -9.16, sixYardEdge, -9.16);
    line(goalLine, 9.16, sixYardEdge, 9.16);
    line(sixYardEdge, -9.16, sixYardEdge, 9.16);
    const spotX = side * (L - 11);
    const reach = Math.acos(5.5 / 9.15);
    if (side < 0) arc(spotX, 0, 9.15, -reach, reach);
    else arc(spotX, 0, 9.15, Math.PI - reach, Math.PI + reach);
    raw.push({ x: spotX, z: 0, spot: true });
  }
  raw.push({ x: 0, z: 0, spot: true });

  const lines = raw.map((point, index) => ({ ...point, glyph: String((index * 7 + 3) % 10) }));
  const field: FieldPoint[] = [];
  for (let x = -L + FIELD_STEP_X / 2; x < L; x += FIELD_STEP_X) {
    for (let z = -W + FIELD_STEP_Z / 2; z < W; z += FIELD_STEP_Z) field.push({ x, z });
  }
  return { lines, field };
}

export type PitchCamera = {
  width: number;
  height: number;
  elapsedSeconds: number;
  drifting: boolean;
};

const TILT_RAD = 1.02;
const DISTANCE = 95;
const BASE_YAW_RAD = -0.18;
const DRIFT_AMPLITUDE_RAD = 0.22;
const DRIFT_RATE = 0.06;

export type Projection = { x: number; y: number; scale: number };

/** Builds a projector for one camera pose, so a frame computes the trig once instead of once per point. */
export function pitchProjector(camera: PitchCamera): (point: FieldPoint) => Projection {
  const yaw = (camera.drifting ? Math.sin(camera.elapsedSeconds * DRIFT_RATE) * DRIFT_AMPLITUDE_RAD : 0) + BASE_YAW_RAD;
  const focal = (camera.width * 0.9 * DISTANCE) / 105;
  const [sinYaw, cosYaw] = [Math.sin(yaw), Math.cos(yaw)];
  const [sinTilt, cosTilt] = [Math.sin(TILT_RAD), Math.cos(TILT_RAD)];
  const centerX = camera.width * 0.5;
  const centerY = camera.height * 0.6;
  return (point) => {
    const rotatedX = point.x * cosYaw - point.z * sinYaw;
    const rotatedZ = point.x * sinYaw + point.z * cosYaw;
    const depth = rotatedZ * cosTilt + DISTANCE;
    return {
      x: centerX + (focal * rotatedX) / depth,
      y: centerY + (focal * -rotatedZ * sinTilt) / depth,
      scale: DISTANCE / depth,
    };
  };
}

/** A perspective projection of a pitch point onto the hero canvas; `scale` is 1 at the centre spot and grows toward the camera. */
export function projectPitch(point: FieldPoint, camera: PitchCamera): Projection {
  return pitchProjector(camera)(point);
}

const SWEEP_SPEED = 0.16;
const SWEEP_START = -PITCH.halfLength - 10;
const SWEEP_WIDTH_METRES = 4;

/** Where the pale sweep sits along the pitch, in metres from the centre line; it restarts from the far end. */
export function sweepX(elapsedSeconds: number): number {
  return ((elapsedSeconds * SWEEP_SPEED) % 1.3) * 105 + SWEEP_START;
}

export function sweepGlow(pointX: number, sweep: number | null): number {
  return sweep === null ? 0 : Math.exp(-(((pointX - sweep) / SWEEP_WIDTH_METRES) ** 2));
}
