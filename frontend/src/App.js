import React, { useState, useEffect, useRef, createContext, useContext, useCallback } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useNavigate, useParams, useSearchParams } from "react-router-dom";
import axios from "axios";
import { Toaster, toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useDropzone } from "react-dropzone";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import JSZip from "jszip";
import { saveAs } from "file-saver";
import { Capacitor } from "@capacitor/core";
import { GoogleAuth } from "@codetrix-studio/capacitor-google-auth";
import {
  Rocket, FileCode, Server, Cloud, Box, Sun, Moon, Plus, ArrowLeft,
  Github, Upload, FileText, Loader2, Check, Copy, Download, FolderTree,
  Database, Cpu, Globe, Settings, ChevronRight, Trash2, RefreshCw,
  Crown, Zap, Users, CreditCard, Star, Lock, X
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// True when running inside the native Android (Capacitor) app rather than a browser.
const IS_NATIVE = Capacitor.isNativePlatform();

// Theme Context
const ThemeContext = createContext();
const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState("dark");
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
};
const useTheme = () => useContext(ThemeContext);

// User Context
const UserContext = createContext();
const UserProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const savedEmail = localStorage.getItem("userEmail");
    if (savedEmail) {
      fetchUser(savedEmail);
    } else {
      setLoading(false);
    }
  }, []);
  
  const fetchUser = async (email) => {
    try {
      const res = await axios.get(`${API}/users/email/${email}`);
      setUser(res.data);
    } catch (e) {
      localStorage.removeItem("userEmail");
    } finally {
      setLoading(false);
    }
  };
  
  const login = async (email, name) => {
    try {
      const res = await axios.post(`${API}/users`, { email, name });
      setUser(res.data);
      localStorage.setItem("userEmail", email);
      return res.data;
    } catch (e) {
      toast.error("Failed to login");
      return null;
    }
  };

  const loginWithGoogle = async (credential) => {
    try {
      const res = await axios.post(`${API}/auth/google`, { credential });
      setUser(res.data);
      localStorage.setItem("userEmail", res.data.email);
      return res.data;
    } catch (e) {
      toast.error("Google login failed");
      return null;
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem("userEmail");
  };
  
  const refreshUser = async () => {
    if (user?.email) {
      await fetchUser(user.email);
    }
  };
  
  return (
    <UserContext.Provider value={{ user, loading, login, loginWithGoogle, logout, refreshUser }}>
      {children}
    </UserContext.Provider>
  );
};
const useUser = () => useContext(UserContext);

// Tier Config
const TIER_ICONS = { free: Zap, pro: Crown, team: Users };
const TIER_COLORS = { 
  free: "text-gray-400", 
  pro: "text-amber-400", 
  team: "text-purple-400" 
};

// Header Component
const Header = () => {
  const { theme, setTheme } = useTheme();
  const { user, logout } = useUser();
  const navigate = useNavigate();
  const [showLogin, setShowLogin] = useState(false);
  
  return (
    <>
      <header className="sticky top-0 z-50 border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center justify-between px-4 md:px-8">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate("/")} data-testid="header-logo">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600">
              <Rocket className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">StackPilot</h1>
              <p className="text-xs text-muted-foreground">Deploy & Docs Copilot</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/pricing")} data-testid="pricing-btn">
              Pricing
            </Button>
            
            {user ? (
              <div className="flex items-center gap-3">
                <Badge variant="outline" className={TIER_COLORS[user.subscription]}>
                  {React.createElement(TIER_ICONS[user.subscription], { className: "h-3 w-3 mr-1" })}
                  {user.subscription.charAt(0).toUpperCase() + user.subscription.slice(1)}
                </Badge>
                <Button variant="ghost" size="sm" onClick={logout} data-testid="logout-btn">
                  Logout
                </Button>
              </div>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setShowLogin(true)} data-testid="login-btn">
                Login
              </Button>
            )}
            
            <Button variant="ghost" size="icon" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} data-testid="theme-toggle">
              {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>
          </div>
        </div>
      </header>
      
      <LoginDialog open={showLogin} onOpenChange={setShowLogin} />
    </>
  );
};

// Login Dialog
const LoginDialog = ({ open, onOpenChange }) => {
  const { login, loginWithGoogle } = useUser();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const googleButtonRef = useRef(null);
  const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

  // Native (Android app): initialize the Google Sign-In plugin once.
  useEffect(() => {
    if (!IS_NATIVE) return;
    try {
      GoogleAuth.initialize({
        clientId: GOOGLE_CLIENT_ID,
        scopes: ["profile", "email"],
        grantOfflineAccess: false,
      });
    } catch (e) {
      // initialize is best-effort; signIn will surface real errors
    }
  }, [GOOGLE_CLIENT_ID]);

  // Web: load Google Identity Services and render the official button.
  useEffect(() => {
    if (IS_NATIVE || !open || !GOOGLE_CLIENT_ID) return;

    const initGoogle = () => {
      if (!window.google?.accounts || !googleButtonRef.current) return;
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleGoogleResponse,
      });
      window.google.accounts.id.renderButton(googleButtonRef.current, {
        theme: "outline",
        size: "large",
        width: googleButtonRef.current.offsetWidth || 360,
        text: "signin_with",
      });
    };

    if (window.google?.accounts) {
      initGoogle();
    } else {
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.onload = initGoogle;
      document.head.appendChild(script);
    }
  }, [open, GOOGLE_CLIENT_ID]);

  const handleGoogleResponse = async (response) => {
    setLoading(true);
    const result = await loginWithGoogle(response.credential);
    setLoading(false);
    if (result) {
      toast.success("Welcome!");
      onOpenChange(false);
    }
  };

  // Native (Android app): trigger the system Google account picker.
  const handleNativeGoogle = async () => {
    setLoading(true);
    try {
      const user = await GoogleAuth.signIn();
      const idToken = user?.authentication?.idToken;
      if (!idToken) throw new Error("No ID token returned");
      const result = await loginWithGoogle(idToken);
      if (result) {
        toast.success("Welcome!");
        onOpenChange(false);
      }
    } catch (e) {
      toast.error("Google login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email) return;
    setLoading(true);
    const result = await login(email, name);
    setLoading(false);
    if (result) {
      toast.success("Welcome!");
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Welcome to StackPilot</DialogTitle>
          <DialogDescription>Sign in to get started</DialogDescription>
        </DialogHeader>

        {IS_NATIVE ? (
          <>
            <Button variant="outline" className="w-full" onClick={handleNativeGoogle} disabled={loading} data-testid="google-signin-native">
              {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Continue with Google
            </Button>
            <div className="relative flex items-center gap-3">
              <Separator className="flex-1" />
              <span className="text-xs text-muted-foreground">or continue with email</span>
              <Separator className="flex-1" />
            </div>
          </>
        ) : GOOGLE_CLIENT_ID ? (
          <>
            <div ref={googleButtonRef} className="flex justify-center w-full" data-testid="google-signin-btn" />
            <div className="relative flex items-center gap-3">
              <Separator className="flex-1" />
              <span className="text-xs text-muted-foreground">or continue with email</span>
              <Separator className="flex-1" />
            </div>
          </>
        ) : null}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Email *</Label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" data-testid="login-email" />
          </div>
          <div className="space-y-2">
            <Label>Name (optional)</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" data-testid="login-name" />
          </div>
          <Button type="submit" className="w-full" disabled={loading || !email} data-testid="login-submit">
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            Continue
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
};

// Upgrade Dialog
const UpgradeDialog = ({ open, onOpenChange, feature }) => {
  const navigate = useNavigate();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5 text-amber-400" />
            Pro Feature
          </DialogTitle>
          <DialogDescription>
            {feature} is available on Pro and Team plans.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="rounded-lg border p-4 bg-secondary/30">
            <h4 className="font-medium mb-2">Pro Plan - $12/month</h4>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Unlimited projects</li>
              <li>• All AI providers (GPT-5.2, Claude, Gemini)</li>
              <li>• ZIP export</li>
              <li>• Unlimited re-analysis</li>
            </ul>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} className="flex-1">Cancel</Button>
            <Button onClick={() => { onOpenChange(false); navigate("/pricing"); }} className="flex-1 bg-gradient-to-r from-amber-500 to-orange-600">
              <Crown className="h-4 w-4 mr-2" />
              Upgrade
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

// Status Badge
const StatusBadge = ({ status }) => {
  const config = {
    pending: { label: "Pending", className: "border-yellow-500/50 text-yellow-500" },
    analyzed: { label: "Analyzed", className: "border-blue-500/50 text-blue-500" },
    plans_generated: { label: "Plans Ready", className: "border-purple-500/50 text-purple-500" },
    docs_generated: { label: "Docs Ready", className: "border-green-500/50 text-green-500" }
  };
  const { label, className } = config[status] || config.pending;
  return <Badge variant="outline" className={className} data-testid={`status-badge-${status}`}>{label}</Badge>;
};

// Pricing Page
const PricingPage = () => {
  const { user } = useUser();
  const navigate = useNavigate();
  const [loadingTier, setLoadingTier] = useState(null);
  const [showLogin, setShowLogin] = useState(false);
  
  const tiers = [
    {
      id: "free",
      name: "Free",
      price: 0,
      description: "Get started with basic features",
      features: ["3 projects", "Gemini AI only", "View docs online", "1 re-analysis per project"],
      limitations: ["No ZIP export", "Limited AI providers"],
      icon: Zap,
      color: "from-gray-500 to-gray-600"
    },
    {
      id: "pro",
      name: "Pro",
      price: 12,
      description: "For professional developers",
      features: ["Unlimited projects", "All AI providers (GPT-5.2, Claude, Gemini)", "ZIP export", "Unlimited re-analysis", "Priority generation"],
      limitations: [],
      icon: Crown,
      color: "from-amber-500 to-orange-600",
      popular: true
    },
    {
      id: "team",
      name: "Team",
      price: 29,
      description: "For teams and organizations",
      features: ["Everything in Pro", "Team collaboration", "Priority support", "Custom templates", "API access"],
      limitations: [],
      icon: Users,
      color: "from-purple-500 to-pink-600"
    }
  ];
  
  const handleUpgrade = async (tier) => {
    if (!user) {
      setShowLogin(true);
      return;
    }
    
    if (tier === "free" || user.subscription === tier) return;
    
    setLoadingTier(tier);
    try {
      const res = await axios.post(`${API}/checkout/create`, {
        userId: user.id,
        tier,
        originUrl: window.location.origin
      });
      window.location.href = res.data.url;
    } catch (e) {
      toast.error("Failed to start checkout");
      setLoadingTier(null);
    }
  };
  
  return (
    <div className="container max-w-6xl py-12 px-4 md:px-8">
      <div className="text-center mb-12">
        <h1 className="text-3xl font-bold mb-3">Simple, Transparent Pricing</h1>
        <p className="text-muted-foreground">Choose the plan that fits your needs</p>
      </div>
      
      <div className="grid gap-6 md:grid-cols-3">
        {tiers.map((tier) => {
          const Icon = tier.icon;
          const isCurrent = user?.subscription === tier.id;
          
          return (
            <Card key={tier.id} className={`relative ${tier.popular ? "border-amber-500/50 shadow-lg shadow-amber-500/10" : ""}`} data-testid={`tier-card-${tier.id}`}>
              {tier.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge className="bg-gradient-to-r from-amber-500 to-orange-600">Most Popular</Badge>
                </div>
              )}
              
              <CardHeader className="text-center pb-2">
                <div className={`mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br ${tier.color}`}>
                  <Icon className="h-6 w-6 text-white" />
                </div>
                <CardTitle>{tier.name}</CardTitle>
                <CardDescription>{tier.description}</CardDescription>
                <div className="mt-4">
                  <span className="text-4xl font-bold">${tier.price}</span>
                  {tier.price > 0 && <span className="text-muted-foreground">/month</span>}
                </div>
              </CardHeader>
              
              <CardContent>
                <ul className="space-y-2">
                  {tier.features.map((feature, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm">
                      <Check className="h-4 w-4 text-green-500" />
                      {feature}
                    </li>
                  ))}
                  {tier.limitations.map((limit, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-muted-foreground">
                      <X className="h-4 w-4 text-red-400" />
                      {limit}
                    </li>
                  ))}
                </ul>
              </CardContent>
              
              <CardFooter>
                <Button
                  className={`w-full ${tier.popular ? "bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700" : ""}`}
                  variant={tier.popular ? "default" : "outline"}
                  onClick={() => handleUpgrade(tier.id)}
                  disabled={isCurrent || loadingTier === tier.id}
                  data-testid={`upgrade-btn-${tier.id}`}
                >
                  {loadingTier === tier.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : isCurrent ? (
                    "Current Plan"
                  ) : tier.price === 0 ? (
                    "Get Started"
                  ) : (
                    <>
                      <CreditCard className="h-4 w-4 mr-2" />
                      Upgrade
                    </>
                  )}
                </Button>
              </CardFooter>
            </Card>
          );
        })}
      </div>
      
      <LoginDialog open={showLogin} onOpenChange={setShowLogin} />
    </div>
  );
};

// Payment Success Page
const PaymentSuccessPage = () => {
  const [searchParams] = useSearchParams();
  const { refreshUser } = useUser();
  const navigate = useNavigate();
  const [status, setStatus] = useState("checking");
  const [attempts, setAttempts] = useState(0);
  
  const checkPayment = useCallback(async () => {
    const sessionId = searchParams.get("session_id");
    if (!sessionId) {
      setStatus("error");
      return;
    }
    
    try {
      const res = await axios.get(`${API}/checkout/status/${sessionId}`);
      if (res.data.paymentStatus === "paid") {
        setStatus("success");
        await refreshUser();
      } else if (res.data.status === "expired") {
        setStatus("expired");
      } else if (attempts < 5) {
        setTimeout(() => setAttempts(a => a + 1), 2000);
      } else {
        setStatus("pending");
      }
    } catch (e) {
      setStatus("error");
    }
  }, [searchParams, refreshUser, attempts]);
  
  useEffect(() => {
    checkPayment();
  }, [checkPayment]);
  
  return (
    <div className="container max-w-lg py-16 px-4">
      <Card>
        <CardContent className="pt-8 text-center">
          {status === "checking" && (
            <>
              <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-primary" />
              <h2 className="text-xl font-semibold mb-2">Processing Payment...</h2>
              <p className="text-muted-foreground">Please wait while we confirm your payment</p>
            </>
          )}
          
          {status === "success" && (
            <>
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-500/20">
                <Check className="h-8 w-8 text-green-500" />
              </div>
              <h2 className="text-xl font-semibold mb-2">Payment Successful!</h2>
              <p className="text-muted-foreground mb-6">Your subscription has been upgraded</p>
              <Button onClick={() => navigate("/")} className="bg-gradient-to-r from-cyan-500 to-blue-600">
                Start Creating Projects
              </Button>
            </>
          )}
          
          {status === "error" && (
            <>
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-500/20">
                <X className="h-8 w-8 text-red-500" />
              </div>
              <h2 className="text-xl font-semibold mb-2">Payment Failed</h2>
              <p className="text-muted-foreground mb-6">Something went wrong. Please try again.</p>
              <Button onClick={() => navigate("/pricing")} variant="outline">Back to Pricing</Button>
            </>
          )}
          
          {status === "expired" && (
            <>
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-yellow-500/20">
                <X className="h-8 w-8 text-yellow-500" />
              </div>
              <h2 className="text-xl font-semibold mb-2">Session Expired</h2>
              <p className="text-muted-foreground mb-6">Your checkout session has expired. Please try again.</p>
              <Button onClick={() => navigate("/pricing")} variant="outline">Back to Pricing</Button>
            </>
          )}
          
          {status === "pending" && (
            <>
              <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-yellow-500" />
              <h2 className="text-xl font-semibold mb-2">Payment Processing</h2>
              <p className="text-muted-foreground mb-6">Your payment is being processed. Check your email for confirmation.</p>
              <Button onClick={() => navigate("/")} variant="outline">Go to Dashboard</Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

// Home Page
const HomePage = () => {
  const navigate = useNavigate();
  const { user } = useUser();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchProjects();
  }, [user]);
  
  const fetchProjects = async () => {
    try {
      const url = user ? `${API}/projects?userId=${user.id}` : `${API}/projects`;
      const res = await axios.get(url);
      setProjects(res.data);
    } catch (e) {
      toast.error("Failed to load projects");
    } finally {
      setLoading(false);
    }
  };
  
  const deleteProject = async (id, e) => {
    e.stopPropagation();
    try {
      await axios.delete(`${API}/projects/${id}`);
      toast.success("Project deleted");
      fetchProjects();
    } catch (e) {
      toast.error("Failed to delete");
    }
  };
  
  const tierLimits = user?.tierLimits || { project_limit: 3, features: ["3 projects", "Gemini AI only"] };
  const projectCount = user?.projectCount || projects.length;
  const canCreateMore = tierLimits.project_limit === -1 || projectCount < tierLimits.project_limit;
  
  return (
    <div className="container max-w-5xl py-8 px-4 md:px-8">
      {/* Hero */}
      <div className="mb-12 text-center">
        <div className="mb-6 inline-flex items-center justify-center">
          <div className="relative">
            <div className="absolute -inset-4 rounded-full bg-gradient-to-r from-cyan-500/20 to-blue-600/20 blur-xl" />
            <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg">
              <Rocket className="h-10 w-10 text-white" />
            </div>
          </div>
        </div>
        <h1 className="mb-3 text-3xl font-bold tracking-tight md:text-4xl">Deployment & Docs Copilot</h1>
        <p className="mx-auto max-w-2xl text-muted-foreground">
          Analyze any codebase, generate deployment plans for Docker, VM, and Serverless, plus comprehensive documentation.
        </p>
      </div>
      
      {/* Usage Stats */}
      {user && (
        <Card className="mb-8" data-testid="usage-card">
          <CardContent className="flex items-center justify-between p-4">
            <div className="flex items-center gap-4">
              <div className={`flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br ${
                user.subscription === "pro" ? "from-amber-500 to-orange-600" : 
                user.subscription === "team" ? "from-purple-500 to-pink-600" : "from-gray-500 to-gray-600"
              }`}>
                {React.createElement(TIER_ICONS[user.subscription], { className: "h-5 w-5 text-white" })}
              </div>
              <div>
                <p className="font-medium">{user.subscription.charAt(0).toUpperCase() + user.subscription.slice(1)} Plan</p>
                <p className="text-sm text-muted-foreground">
                  {tierLimits.project_limit === -1 ? "Unlimited projects" : `${projectCount}/${tierLimits.project_limit} projects used`}
                </p>
              </div>
            </div>
            {user.subscription === "free" && (
              <Button variant="outline" size="sm" onClick={() => navigate("/pricing")} data-testid="upgrade-cta">
                <Crown className="h-4 w-4 mr-2 text-amber-400" />
                Upgrade
              </Button>
            )}
          </CardContent>
        </Card>
      )}
      
      {/* New Project Button */}
      <div className="mb-8 flex justify-center">
        <Button 
          size="lg" 
          onClick={() => canCreateMore ? navigate("/new") : toast.error("Project limit reached. Upgrade to Pro!")}
          className={`gap-2 ${canCreateMore ? "bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700" : "opacity-50"}`}
          data-testid="new-project-btn"
        >
          <Plus className="h-5 w-5" />
          New Project
          {!canCreateMore && <Lock className="h-4 w-4 ml-1" />}
        </Button>
      </div>
      
      {/* Projects List */}
      <div>
        <h2 className="mb-4 text-lg font-semibold">Recent Projects</h2>
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : projects.length === 0 ? (
          <Card className="border-dashed" data-testid="empty-projects">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <FolderTree className="mb-4 h-12 w-12 text-muted-foreground/50" />
              <p className="text-muted-foreground">No projects yet. Create your first one!</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            {projects.map((project) => (
              <Card 
                key={project.id} 
                className="cursor-pointer transition-all hover:border-primary/50 hover:shadow-md"
                onClick={() => navigate(`/project/${project.id}`)}
                data-testid={`project-card-${project.id}`}
              >
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary">
                      {project.sourceType === "github_url" ? <Github className="h-5 w-5" /> : 
                       project.sourceType === "upload" ? <Upload className="h-5 w-5" /> : <FileText className="h-5 w-5" />}
                    </div>
                    <div>
                      <h3 className="font-medium">{project.name}</h3>
                      <p className="text-sm text-muted-foreground">
                        {project.sourceType === "github_url" ? project.sourceUrl : 
                         project.sourceType === "upload" ? "Uploaded ZIP" : "Text Description"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={project.status} />
                    <Button variant="ghost" size="icon" onClick={(e) => deleteProject(project.id, e)} data-testid={`delete-project-${project.id}`}>
                      <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                    </Button>
                    <ChevronRight className="h-5 w-5 text-muted-foreground" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// Input Project Page
const InputProjectPage = () => {
  const navigate = useNavigate();
  const { user } = useUser();
  const [formData, setFormData] = useState({
    name: "", sourceType: "github_url", sourceUrl: "", textDescription: "",
    aiProvider: "gemini", useEmergentKey: true, techStackHints: []
  });
  const [uploadedFile, setUploadedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [showUpgrade, setShowUpgrade] = useState(false);
  const [upgradeFeature, setUpgradeFeature] = useState("");
  
  const tierLimits = user?.tierLimits || { ai_providers: ["gemini"] };
  const allowedProviders = tierLimits.ai_providers || ["gemini"];
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { "application/zip": [".zip"] },
    maxFiles: 1,
    onDrop: (files) => setUploadedFile(files[0])
  });
  
  const handleProviderChange = (provider) => {
    if (!allowedProviders.includes(provider)) {
      setUpgradeFeature(`${provider.toUpperCase()} AI provider`);
      setShowUpgrade(true);
      return;
    }
    setFormData({ ...formData, aiProvider: provider });
  };
  
  const handleSubmit = async () => {
    if (!formData.name.trim()) { toast.error("Project name required"); return; }
    if (formData.sourceType === "github_url" && !formData.sourceUrl) { toast.error("GitHub URL required"); return; }
    if (formData.sourceType === "github_url" && !formData.sourceUrl.includes("github.com")) { toast.error("Please enter a valid GitHub URL"); return; }
    if (formData.sourceType === "upload" && !uploadedFile) { toast.error("Upload a ZIP file"); return; }
    if (formData.sourceType === "text_only" && !formData.textDescription.trim()) { toast.error("Project description required for text-only mode"); return; }
    
    setLoading(true);
    setProgress(10);
    
    try {
      const projectRes = await axios.post(`${API}/projects`, { ...formData, userId: user?.id });
      const projectId = projectRes.data.id;
      setProgress(30);
      
      if (formData.sourceType === "upload" && uploadedFile) {
        const fd = new FormData();
        fd.append("file", uploadedFile);
        await axios.post(`${API}/projects/${projectId}/upload`, fd);
        setProgress(50);
      }
      
      setAnalyzing(true);
      setProgress(60);
      await axios.post(`${API}/projects/${projectId}/analyze`);
      setProgress(100);
      
      toast.success("Project analyzed!");
      navigate(`/project/${projectId}`);
    } catch (e) {
      const msg = e.response?.data?.detail || "Failed to create project";
      if (msg.includes("limit")) {
        setUpgradeFeature("More projects");
        setShowUpgrade(true);
      } else if (msg.includes("provider")) {
        setUpgradeFeature("This AI provider");
        setShowUpgrade(true);
      } else {
        toast.error(msg);
      }
    } finally {
      setLoading(false);
      setAnalyzing(false);
    }
  };
  
  return (
    <div className="container max-w-3xl py-8 px-4 md:px-8">
      <Button variant="ghost" className="mb-6 gap-2" onClick={() => navigate("/")} data-testid="back-btn">
        <ArrowLeft className="h-4 w-4" /> Back
      </Button>
      
      <Card data-testid="input-project-card">
        <CardHeader>
          <CardTitle>New Project</CardTitle>
          <CardDescription>Configure your project for analysis</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label>Project Name *</Label>
            <Input value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="my-awesome-project" data-testid="project-name-input" />
          </div>
          
          <div className="space-y-2">
            <Label>Source Type</Label>
            <Tabs value={formData.sourceType} onValueChange={(v) => setFormData({ ...formData, sourceType: v })}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="github_url" className="gap-2" data-testid="tab-github"><Github className="h-4 w-4" />GitHub URL</TabsTrigger>
                <TabsTrigger value="upload" className="gap-2" data-testid="tab-upload"><Upload className="h-4 w-4" />Upload ZIP</TabsTrigger>
                <TabsTrigger value="text_only" className="gap-2" data-testid="tab-text"><FileText className="h-4 w-4" />Text Only</TabsTrigger>
              </TabsList>
              
              <TabsContent value="github_url" className="mt-4">
                <Input placeholder="https://github.com/user/repo" value={formData.sourceUrl} onChange={(e) => setFormData({ ...formData, sourceUrl: e.target.value })} data-testid="github-url-input" />
              </TabsContent>
              
              <TabsContent value="upload" className="mt-4">
                <div {...getRootProps()} className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"}`} data-testid="file-dropzone">
                  <input {...getInputProps()} />
                  <Upload className="mb-3 h-8 w-8 text-muted-foreground" />
                  {uploadedFile ? <p className="text-sm font-medium">{uploadedFile.name}</p> : <p className="text-sm text-muted-foreground">Drag & drop ZIP file here, or click to select</p>}
                </div>
              </TabsContent>

              <TabsContent value="text_only" className="mt-4">
                <p className="text-sm text-muted-foreground">Describe your project below — no code upload needed. The AI will generate plans and docs based on your description.</p>
              </TabsContent>
            </Tabs>
          </div>

          <div className="space-y-2">
            <Label>{formData.sourceType === "text_only" ? "Project Description *" : "Additional Context (Optional)"}</Label>
            <Textarea
              placeholder={formData.sourceType === "text_only" ? "Describe your project in detail: tech stack, architecture, deployment targets..." : "Describe your project..."}
              value={formData.textDescription}
              onChange={(e) => setFormData({ ...formData, textDescription: e.target.value })}
              rows={formData.sourceType === "text_only" ? 5 : 3}
              data-testid="text-description-input"
            />
          </div>
          
          <Separator />
          
          <div className="space-y-2">
            <Label>AI Provider</Label>
            <Select value={formData.aiProvider} onValueChange={handleProviderChange}>
              <SelectTrigger data-testid="ai-provider-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="gemini">Gemini (Google)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          {loading && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>{analyzing ? "Analyzing codebase..." : "Creating project..."}</span>
                <span>{progress}%</span>
              </div>
              <Progress value={progress} />
            </div>
          )}
          
          <Button className="w-full gap-2 bg-gradient-to-r from-cyan-500 to-blue-600" size="lg" onClick={handleSubmit} disabled={loading} data-testid="analyze-project-btn">
            {loading ? <><Loader2 className="h-5 w-5 animate-spin" />{analyzing ? "Analyzing..." : "Creating..."}</> : <><Rocket className="h-5 w-5" />Analyze Project</>}
          </Button>
        </CardContent>
      </Card>
      
      <UpgradeDialog open={showUpgrade} onOpenChange={setShowUpgrade} feature={upgradeFeature} />
    </div>
  );
};

// Project Detail Page
const ProjectDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useUser();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState("analysis");
  const [reanalyzing, setReanalyzing] = useState(false);
  const [showUpgrade, setShowUpgrade] = useState(false);
  const [upgradeFeature, setUpgradeFeature] = useState("");
  
  useEffect(() => { fetchProject(); }, [id]);
  
  const fetchProject = async () => {
    try {
      const res = await axios.get(`${API}/projects/${id}`);
      setProject(res.data);
      if (res.data.status === "docs_generated") setActiveTab("docs");
      else if (res.data.status === "plans_generated") setActiveTab("plans");
    } catch (e) {
      toast.error("Failed to load project");
      navigate("/");
    } finally {
      setLoading(false);
    }
  };
  
  const handleGenerate = async (type) => {
    setGenerating(true);
    try {
      const res = await axios.post(`${API}/projects/${id}/generate`, { projectId: id, generateType: type });
      setProject(res.data);
      toast.success(type === "both" ? "Plans & docs generated!" : `${type} generated!`);
      setActiveTab(type === "plans" ? "plans" : "docs");
    } catch (e) {
      toast.error("Generation failed");
    } finally {
      setGenerating(false);
    }
  };
  
  const handleReanalyze = async () => {
    setReanalyzing(true);
    try {
      const res = await axios.post(`${API}/projects/${id}/analyze?reanalyze=true`);
      setProject(res.data);
      toast.success("Re-analysis complete!");
    } catch (e) {
      const msg = e.response?.data?.detail || "Re-analysis failed";
      if (msg.includes("limit")) {
        setUpgradeFeature("Unlimited re-analysis");
        setShowUpgrade(true);
      } else {
        toast.error(msg);
      }
    } finally {
      setReanalyzing(false);
    }
  };
  
  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied`);
  };
  
  const exportAsZip = async () => {
    // Check export permission
    const tierLimits = user?.tierLimits || { can_export_zip: false };
    if (!tierLimits.can_export_zip) {
      setUpgradeFeature("ZIP export");
      setShowUpgrade(true);
      return;
    }
    
    if (!project?.docs) return;
    
    const zip = new JSZip();
    zip.file("README.md", project.docs.readme || "");
    const docsFolder = zip.folder("docs");
    docsFolder.file("user-guide.md", project.docs.userGuide || "");
    docsFolder.file("frontend-guide.md", project.docs.frontendGuide || "");
    docsFolder.file("backend-guide.md", project.docs.backendGuide || "");
    docsFolder.file("deployment-guide.md", project.docs.deploymentGuide || "");
    
    if (project.deploymentPlans?.dockerPlan) {
      const scriptsFolder = zip.folder("scripts");
      scriptsFolder.file("docker-deployment.md", project.deploymentPlans.dockerPlan);
      scriptsFolder.file("vm-deployment.md", project.deploymentPlans.vmPlan || "");
      scriptsFolder.file("serverless-deployment.md", project.deploymentPlans.serverlessPlan || "");
    }
    
    const content = await zip.generateAsync({ type: "blob" });
    saveAs(content, `${project.name}-deployment-docs.zip`);
    toast.success("ZIP exported!");
  };
  
  if (loading) return <div className="flex h-[50vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>;
  if (!project) return null;
  
  const { detectedTechStack, buildSteps, configFiles, envVars, deploymentPlans, docs } = project;
  const tierLimits = user?.tierLimits || { can_export_zip: false };
  
  return (
    <div className="container max-w-6xl py-8 px-4 md:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate("/")} data-testid="back-btn"><ArrowLeft className="h-5 w-5" /></Button>
          <div>
            <h1 className="text-2xl font-bold">{project.name}</h1>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {project.sourceType === "github_url" ? <><Github className="h-4 w-4" /> {project.sourceUrl}</> : 
               project.sourceType === "upload" ? <><Upload className="h-4 w-4" /> Uploaded ZIP</> : <><FileText className="h-4 w-4" /> Text</>}
            </div>
          </div>
        </div>
        <StatusBadge status={project.status} />
      </div>
      
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="analysis" className="gap-2" data-testid="tab-analysis"><Settings className="h-4 w-4" />Analysis</TabsTrigger>
          <TabsTrigger value="plans" className="gap-2" data-testid="tab-plans"><Server className="h-4 w-4" />Deployment Plans</TabsTrigger>
          <TabsTrigger value="docs" className="gap-2" data-testid="tab-docs"><FileCode className="h-4 w-4" />Documentation</TabsTrigger>
        </TabsList>
        
        <TabsContent value="analysis">
          <div className="grid gap-6 md:grid-cols-2">
            <Card data-testid="tech-stack-card">
              <CardHeader><CardTitle className="flex items-center gap-2"><Cpu className="h-5 w-5" />Detected Tech Stack</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                {["frontend", "backend", "database", "infra", "services"].map(key => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground capitalize">{key}</span>
                    <Badge variant="secondary">{detectedTechStack?.[key] || "Not detected"}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
            
            <Card data-testid="build-steps-card">
              <CardHeader><CardTitle className="flex items-center gap-2"><Globe className="h-5 w-5" />Build Steps</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="mb-1 text-sm text-muted-foreground">Frontend Build</p>
                  <code className="block rounded bg-secondary p-2 text-sm">{buildSteps?.frontendBuild || "N/A"}</code>
                </div>
                <div>
                  <p className="mb-1 text-sm text-muted-foreground">Backend Build</p>
                  <code className="block rounded bg-secondary p-2 text-sm">{buildSteps?.backendBuild || "N/A"}</code>
                </div>
              </CardContent>
            </Card>
            
            <Card><CardHeader><CardTitle className="flex items-center gap-2"><FileCode className="h-5 w-5" />Config Files</CardTitle></CardHeader>
              <CardContent><div className="flex flex-wrap gap-2">{configFiles?.length > 0 ? configFiles.map(f => <Badge key={f} variant="outline">{f}</Badge>) : <p className="text-sm text-muted-foreground">None</p>}</div></CardContent>
            </Card>
            
            <Card><CardHeader><CardTitle className="flex items-center gap-2"><Database className="h-5 w-5" />Env Variables</CardTitle></CardHeader>
              <CardContent><div className="flex flex-wrap gap-2">{envVars?.length > 0 ? envVars.map(v => <Badge key={v} variant="outline">{v}</Badge>) : <p className="text-sm text-muted-foreground">None</p>}</div></CardContent>
            </Card>
          </div>
          
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            <Button variant="outline" onClick={() => handleGenerate("plans")} disabled={generating} data-testid="generate-plans-btn"><Server className="mr-2 h-4 w-4" />Generate Plans</Button>
            <Button variant="outline" onClick={() => handleGenerate("docs")} disabled={generating} data-testid="generate-docs-btn"><FileCode className="mr-2 h-4 w-4" />Generate Docs</Button>
            <Button className="gap-2 bg-gradient-to-r from-cyan-500 to-blue-600" onClick={() => handleGenerate("both")} disabled={generating} data-testid="generate-both-btn">
              {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
              Generate Both (Recommended)
            </Button>
          </div>
          
          <div className="mt-4 flex justify-center">
            <Button variant="ghost" size="sm" onClick={handleReanalyze} disabled={reanalyzing} data-testid="reanalyze-btn">
              <RefreshCw className={`mr-2 h-4 w-4 ${reanalyzing ? "animate-spin" : ""}`} />Re-analyze
            </Button>
          </div>
        </TabsContent>
        
        <TabsContent value="plans">
          {!deploymentPlans?.genericPlan ? (
            <Card className="border-dashed"><CardContent className="flex flex-col items-center justify-center py-12">
              <Server className="mb-4 h-12 w-12 text-muted-foreground/50" />
              <p className="mb-4 text-muted-foreground">No deployment plans yet</p>
              <Button onClick={() => handleGenerate("plans")} disabled={generating}>{generating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Generate Plans</Button>
            </CardContent></Card>
          ) : (
            <div className="space-y-6">
              {[
                { key: "genericPlan", title: "Generic Plan", icon: Globe, desc: "Universal steps" },
                { key: "dockerPlan", title: "Docker Plan", icon: Box, desc: "Containerized" },
                { key: "vmPlan", title: "VM/Server Plan", icon: Server, desc: "Linux server" },
                { key: "serverlessPlan", title: "Serverless/PaaS", icon: Cloud, desc: "Cloud platform" }
              ].map(({ key, title, icon: Icon, desc }) => (
                <Card key={key} data-testid={`plan-card-${key}`}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2"><Icon className="h-5 w-5" />{title}</CardTitle>
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(deploymentPlans[key], title)}><Copy className="mr-2 h-4 w-4" />Copy</Button>
                    </div>
                    <CardDescription>{desc}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[300px] rounded-lg border bg-secondary/30 p-4">
                      <div className="prose prose-sm dark:prose-invert max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{deploymentPlans[key]}</ReactMarkdown></div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              ))}
              
              <div className="flex justify-center">
                <Button onClick={exportAsZip} className="gap-2" data-testid="export-scripts-btn">
                  <Download className="h-4 w-4" />
                  Export Scripts
                  {!tierLimits.can_export_zip && <Lock className="h-4 w-4 ml-1" />}
                </Button>
              </div>
            </div>
          )}
        </TabsContent>
        
        <TabsContent value="docs">
          {!docs?.readme ? (
            <Card className="border-dashed"><CardContent className="flex flex-col items-center justify-center py-12">
              <FileCode className="mb-4 h-12 w-12 text-muted-foreground/50" />
              <p className="mb-4 text-muted-foreground">No documentation yet</p>
              <Button onClick={() => handleGenerate("docs")} disabled={generating}>{generating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Generate Docs</Button>
            </CardContent></Card>
          ) : (
            <div className="space-y-6">
              {[
                { key: "readme", title: "README.md", desc: "Project overview" },
                { key: "userGuide", title: "user-guide.md", desc: "End-user docs" },
                { key: "frontendGuide", title: "frontend-guide.md", desc: "Frontend guide" },
                { key: "backendGuide", title: "backend-guide.md", desc: "Backend guide" },
                { key: "deploymentGuide", title: "deployment-guide.md", desc: "Deployment guide" }
              ].map(({ key, title, desc }) => (
                <Card key={key} data-testid={`doc-card-${key}`}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2"><FileCode className="h-5 w-5" />{title}</CardTitle>
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(docs[key], title)}><Copy className="mr-2 h-4 w-4" />Copy</Button>
                    </div>
                    <CardDescription>{desc}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[300px] rounded-lg border bg-secondary/30 p-4">
                      <div className="prose prose-sm dark:prose-invert max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{docs[key]}</ReactMarkdown></div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              ))}
              
              <div className="flex flex-wrap justify-center gap-4">
                <Button onClick={exportAsZip} className="gap-2" data-testid="export-zip-btn">
                  <Download className="h-4 w-4" />
                  Export as ZIP
                  {!tierLimits.can_export_zip && <Lock className="h-4 w-4 ml-1" />}
                </Button>
              </div>
              
              <Card data-testid="repo-structure-card">
                <CardHeader><CardTitle className="flex items-center gap-2"><FolderTree className="h-5 w-5" />Export Structure</CardTitle></CardHeader>
                <CardContent>
                  <pre className="rounded-lg bg-secondary p-4 text-sm">{`/${project.name}/
├── README.md
├── docs/
│   ├── user-guide.md
│   ├── frontend-guide.md
│   ├── backend-guide.md
│   └── deployment-guide.md
└── scripts/
    ├── docker-deployment.md
    ├── vm-deployment.md
    └── serverless-deployment.md`}</pre>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>
      </Tabs>
      
      <UpgradeDialog open={showUpgrade} onOpenChange={setShowUpgrade} feature={upgradeFeature} />
    </div>
  );
};

// Main App
function App() {
  return (
    <ThemeProvider>
      <UserProvider>
        <div className="min-h-screen bg-background">
          <BrowserRouter>
            <Header />
            <main>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/new" element={<InputProjectPage />} />
                <Route path="/project/:id" element={<ProjectDetailPage />} />
                <Route path="/pricing" element={<PricingPage />} />
                <Route path="/payment/success" element={<PaymentSuccessPage />} />
              </Routes>
            </main>
          </BrowserRouter>
          <Toaster position="bottom-right" richColors />
        </div>
      </UserProvider>
    </ThemeProvider>
  );
}

export default App;
