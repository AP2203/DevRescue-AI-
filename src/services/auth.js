/**
 * DevRescue AI - Authentication Service (Delegated to AuthContext)
 * Standardized single frontend demo authentication layer.
 */

export const DEMO_USER = {
  id: 'usr-ansh',
  name: 'Ansh',
  email: 'ansh@devrescue.ai',
  role: 'Staff Engineer',
  avatar_url: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80',
  github_username: 'ansh-dev',
  isDemo: true,
};

export const authService = {
  getUser: () => DEMO_USER,
  signInWithEmail: async (email) => ({
    data: { user: { ...DEMO_USER, email: email || DEMO_USER.email } },
    error: null,
  }),
  signOut: async () => ({ error: null }),
};

export default authService;
