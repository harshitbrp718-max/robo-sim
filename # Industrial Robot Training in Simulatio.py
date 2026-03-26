# Industrial Robot Training in Simulation (Robust Version)
# FIXES:
# - Handles missing numpy
# - Handles missing pybullet
# - Handles missing gym/gymnasium
# - Adds fallback "mock simulation" so code never crashes

# ---------- SAFE IMPORTS ----------

# NumPy
try:
    import numpy as np
except ImportError:
    print("ERROR: numpy not installed. Run: pip install numpy")
    raise

# PyBullet (physics engine)
try:
    import pybullet as p
    import pybullet_data
    PYBULLET_AVAILABLE = True
except ImportError:
    print("WARNING: pybullet not installed. Running in MOCK mode.")
    PYBULLET_AVAILABLE = False

# Gym / Gymnasium
try:
    import gymnasium as gym
    from gymnasium import spaces
    GYM_AVAILABLE = True
except ImportError:
    try:
        import gym
        from gym import spaces
        GYM_AVAILABLE = True
    except ImportError:
        GYM_AVAILABLE = False

# Minimal fallback for spaces
if not GYM_AVAILABLE:
    class Box:
        def __init__(self, low, high, shape, dtype):
            self.low = low
            self.high = high
            self.shape = shape
            self.dtype = dtype

    class spaces:
        Box = Box

    class BaseEnv:
        pass
else:
    BaseEnv = gym.Env

# Try Stable-Baselines3
try:
    from stable_baselines3 import PPO
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False
    print("WARNING: stable-baselines3 not installed. Training disabled.")

# ---------- ENVIRONMENT ----------

class RobotReachEnv(BaseEnv):
    def __init__(self):
        super().__init__()

        self.action_space = spaces.Box(low=-1, high=1, shape=(3,), dtype=np.float32)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(6,), dtype=np.float32)

        if PYBULLET_AVAILABLE:
            self.physics_client = p.connect(p.DIRECT)
            p.setAdditionalSearchPath(pybullet_data.getDataPath())
        else:
            self.robot_pos = np.zeros(3)

    def reset(self):
        if PYBULLET_AVAILABLE:
            p.resetSimulation()
            p.setGravity(0, 0, -9.8)

            self.plane = p.loadURDF("plane.urdf")
            self.robot = p.loadURDF("kuka_iiwa/model.urdf", useFixedBase=True)

        else:
            self.robot_pos = np.zeros(3)

        self.target = np.random.uniform(low=-0.5, high=0.5, size=(3,))

        obs = self._get_obs()

        if GYM_AVAILABLE:
            return obs, {}
        return obs

    def step(self, action):
        action = np.array(action, dtype=np.float32)

        if PYBULLET_AVAILABLE:
            for i in range(3):
                p.setJointMotorControl2(self.robot, i, p.POSITION_CONTROL, targetPosition=float(action[i]))
            p.stepSimulation()
        else:
            # Mock movement (simple physics-free update)
            self.robot_pos += action * 0.05

        obs = self._get_obs()
        distance = np.linalg.norm(obs[:3] - obs[3:])
        reward = -distance
        done = distance < 0.05

        if GYM_AVAILABLE:
            return obs, reward, done, False, {}
        return obs, reward, done, {}

    def _get_obs(self):
        if PYBULLET_AVAILABLE:
            end_effector_pos = p.getLinkState(self.robot, 6)[0]
        else:
            end_effector_pos = self.robot_pos

        return np.array(list(end_effector_pos) + list(self.target), dtype=np.float32)

    def close(self):
        if PYBULLET_AVAILABLE:
            p.disconnect()

# ---------- TESTS ----------

def test_environment_runs():
    env = RobotReachEnv()
    result = env.reset()

    obs = result[0] if GYM_AVAILABLE else result

    assert len(obs) == 6, "Observation must be length 6"

    for _ in range(10):
        action = np.zeros(3)
        result = env.step(action)
        assert result is not None, "Step should return output"

    env.close()
    print("✓ Environment basic test passed")


def test_random_actions():
    env = RobotReachEnv()
    result = env.reset()

    obs = result[0] if GYM_AVAILABLE else result

    for _ in range(10):
        action = np.random.uniform(-1, 1, size=3)
        result = env.step(action)
        obs = result[0]

    assert obs.shape[0] == 6, "Observation shape incorrect"

    env.close()
    print("✓ Random action test passed")

# Run tests
if __name__ == "__main__":
    test_environment_runs()
    test_random_actions()

# ---------- TRAINING ----------

if GYM_AVAILABLE and SB3_AVAILABLE and PYBULLET_AVAILABLE:
    env = RobotReachEnv()

    model = PPO("MlpPolicy", env, verbose=1)
    model.learn(total_timesteps=3000)

    model.save("robot_reach_model")

    obs, _ = env.reset()
    for _ in range(100):
        action, _ = model.predict(obs)
        obs, reward, done, _, _ = env.step(action)
        if done:
            print("Target reached!")
            break

    env.close()
else:
    print("\nTraining skipped due to missing dependencies.")
    print("To enable full training install:")
    print("pip install numpy pybullet gymnasium stable-baselines3")
