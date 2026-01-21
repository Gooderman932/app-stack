import { useState, useEffect, createContext, useContext } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { Toaster, toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import { useDropzone } from "react-dropzone";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import JSZip from "jszip";
import { saveAs } from "file-saver";
import {
  Rocket, FileCode, Server, Cloud, Box, Sun, Moon, Plus, ArrowLeft,
  Github, Upload, FileText, Loader2, Check, Copy, Download, FolderTree,
  Database, Cpu, Globe, Settings, ChevronRight, Trash2, RefreshCw
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Theme Context
const ThemeContext = createContext();

const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState("dark");
  
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  
  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

const useTheme = () => useContext(ThemeContext);

// Header Component
const Header = () => {
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();
  
  return (
    <header className="sticky top-0 z-50 border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between px-4 md:px-8">
        <div 
          className="flex items-center gap-3 cursor-pointer" 
          onClick={() => navigate("/")}
          data-testid="header-logo"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600">
            <Rocket className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight">StackPilot</h1>
            <p className="text-xs text-muted-foreground">Deploy & Docs Copilot</p>
          </div>
        </div>
        
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          data-testid="theme-toggle"
        >
          {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>
      </div>
    </header>
  );
};

// Status Badge Component
const StatusBadge = ({ status }) => {
  const config = {
    pending: { label: "Pending", variant: "outline", className: "border-yellow-500/50 text-yellow-500" },
    analyzed: { label: "Analyzed", variant: "outline", className: "border-blue-500/50 text-blue-500" },
    plans_generated: { label: "Plans Ready", variant: "outline", className: "border-purple-500/50 text-purple-500" },
    docs_generated: { label: "Docs Ready", variant: "outline", className: "border-green-500/50 text-green-500" }
  };
  const { label, className } = config[status] || config.pending;
  
  return <Badge variant="outline" className={className} data-testid={`status-badge-${status}`}>{label}</Badge>;
};

// Home Page
const HomePage = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchProjects();
  }, []);
  
  const fetchProjects = async () => {
    try {
      const res = await axios.get(`${API}/projects`);
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
      toast.error("Failed to delete project");
    }
  };
  
  return (
    <div className="container max-w-5xl py-8 px-4 md:px-8">
      {/* Hero Section */}
      <div className="mb-12 text-center">
        <div className="mb-6 inline-flex items-center justify-center">
          <div className="relative">
            <div className="absolute -inset-4 rounded-full bg-gradient-to-r from-cyan-500/20 to-blue-600/20 blur-xl" />
            <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg">
              <Rocket className="h-10 w-10 text-white" />
            </div>
          </div>
        </div>
        <h1 className="mb-3 text-3xl font-bold tracking-tight md:text-4xl">
          Deployment & Docs Copilot
        </h1>
        <p className="mx-auto max-w-2xl text-muted-foreground">
          Analyze any codebase, generate deployment plans for Docker, VM, and Serverless,
          plus comprehensive documentation—all in one click.
        </p>
      </div>
      
      {/* New Project Button */}
      <div className="mb-8 flex justify-center">
        <Button 
          size="lg" 
          onClick={() => navigate("/new")}
          className="gap-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700"
          data-testid="new-project-btn"
        >
          <Plus className="h-5 w-5" />
          New Project
        </Button>
      </div>
      
      {/* Recent Projects */}
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
                      {project.sourceType === "github_url" ? (
                        <Github className="h-5 w-5" />
                      ) : project.sourceType === "upload" ? (
                        <Upload className="h-5 w-5" />
                      ) : (
                        <FileText className="h-5 w-5" />
                      )}
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
                    <Button 
                      variant="ghost" 
                      size="icon"
                      onClick={(e) => deleteProject(project.id, e)}
                      data-testid={`delete-project-${project.id}`}
                    >
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
  const [formData, setFormData] = useState({
    name: "",
    sourceType: "github_url",
    sourceUrl: "",
    textDescription: "",
    aiProvider: "gpt_5_2",
    useEmergentKey: true,
    techStackHints: []
  });
  const [uploadedFile, setUploadedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { "application/zip": [".zip"] },
    maxFiles: 1,
    onDrop: (files) => setUploadedFile(files[0])
  });
  
  const handleSubmit = async () => {
    if (!formData.name.trim()) {
      toast.error("Project name is required");
      return;
    }
    
    if (formData.sourceType === "github_url" && !formData.sourceUrl) {
      toast.error("GitHub URL is required");
      return;
    }
    
    if (formData.sourceType === "upload" && !uploadedFile) {
      toast.error("Please upload a ZIP file");
      return;
    }
    
    setLoading(true);
    setProgress(10);
    
    try {
      // Create project
      const projectRes = await axios.post(`${API}/projects`, formData);
      const projectId = projectRes.data.id;
      setProgress(30);
      
      // Upload file if needed
      if (formData.sourceType === "upload" && uploadedFile) {
        const fd = new FormData();
        fd.append("file", uploadedFile);
        await axios.post(`${API}/projects/${projectId}/upload`, fd);
        setProgress(50);
      }
      
      // Analyze project
      setAnalyzing(true);
      setProgress(60);
      await axios.post(`${API}/projects/${projectId}/analyze`);
      setProgress(100);
      
      toast.success("Project analyzed successfully!");
      navigate(`/project/${projectId}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to create project");
    } finally {
      setLoading(false);
      setAnalyzing(false);
    }
  };
  
  const hints = ["Frontend", "Backend", "Database", "Infra"];
  
  return (
    <div className="container max-w-3xl py-8 px-4 md:px-8">
      <Button 
        variant="ghost" 
        className="mb-6 gap-2" 
        onClick={() => navigate("/")}
        data-testid="back-btn"
      >
        <ArrowLeft className="h-4 w-4" />
        Back
      </Button>
      
      <Card data-testid="input-project-card">
        <CardHeader>
          <CardTitle>New Project</CardTitle>
          <CardDescription>Configure your project for analysis</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Project Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Project Name *</Label>
            <Input
              id="name"
              placeholder="my-awesome-project"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              data-testid="project-name-input"
            />
          </div>
          
          {/* Source Type Tabs */}
          <div className="space-y-2">
            <Label>Source Type</Label>
            <Tabs 
              value={formData.sourceType} 
              onValueChange={(v) => setFormData({ ...formData, sourceType: v })}
            >
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="github_url" className="gap-2" data-testid="tab-github">
                  <Github className="h-4 w-4" />
                  GitHub URL
                </TabsTrigger>
                <TabsTrigger value="upload" className="gap-2" data-testid="tab-upload">
                  <Upload className="h-4 w-4" />
                  Upload ZIP
                </TabsTrigger>
                <TabsTrigger value="text_only" className="gap-2" data-testid="tab-text">
                  <FileText className="h-4 w-4" />
                  Text Only
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="github_url" className="mt-4">
                <Input
                  placeholder="https://github.com/user/repo"
                  value={formData.sourceUrl}
                  onChange={(e) => setFormData({ ...formData, sourceUrl: e.target.value })}
                  data-testid="github-url-input"
                />
              </TabsContent>
              
              <TabsContent value="upload" className="mt-4">
                <div
                  {...getRootProps()}
                  className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors
                    ${isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"}`}
                  data-testid="file-dropzone"
                >
                  <input {...getInputProps()} />
                  <Upload className="mb-3 h-8 w-8 text-muted-foreground" />
                  {uploadedFile ? (
                    <p className="text-sm font-medium">{uploadedFile.name}</p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Drag & drop ZIP file here, or click to select
                    </p>
                  )}
                </div>
              </TabsContent>
              
              <TabsContent value="text_only" className="mt-4">
                <p className="mb-2 text-sm text-muted-foreground">
                  Describe your project structure and tech stack
                </p>
              </TabsContent>
            </Tabs>
          </div>
          
          {/* Text Description */}
          <div className="space-y-2">
            <Label htmlFor="description">Additional Context (Optional)</Label>
            <Textarea
              id="description"
              placeholder="Describe your project, special requirements, or deployment preferences..."
              value={formData.textDescription}
              onChange={(e) => setFormData({ ...formData, textDescription: e.target.value })}
              rows={4}
              data-testid="text-description-input"
            />
          </div>
          
          {/* Tech Stack Hints */}
          <div className="space-y-2">
            <Label>Tech Stack Hints (Optional)</Label>
            <div className="flex flex-wrap gap-2">
              {hints.map((hint) => (
                <Badge
                  key={hint}
                  variant={formData.techStackHints.includes(hint) ? "default" : "outline"}
                  className="cursor-pointer"
                  onClick={() => {
                    const newHints = formData.techStackHints.includes(hint)
                      ? formData.techStackHints.filter(h => h !== hint)
                      : [...formData.techStackHints, hint];
                    setFormData({ ...formData, techStackHints: newHints });
                  }}
                  data-testid={`hint-${hint.toLowerCase()}`}
                >
                  {hint}
                </Badge>
              ))}
            </div>
          </div>
          
          <Separator />
          
          {/* AI Provider */}
          <div className="space-y-2">
            <Label>AI Provider</Label>
            <Select
              value={formData.aiProvider}
              onValueChange={(v) => setFormData({ ...formData, aiProvider: v })}
            >
              <SelectTrigger data-testid="ai-provider-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="gpt_5_2">GPT-5.2 (OpenAI)</SelectItem>
                <SelectItem value="claude">Claude (Anthropic)</SelectItem>
                <SelectItem value="gemini">Gemini (Google)</SelectItem>
                <SelectItem value="emergent_default">Emergent Default</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          {/* Emergent Key Toggle */}
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label>Use Emergent LLM Key</Label>
              <p className="text-sm text-muted-foreground">
                Use the universal key for AI analysis
              </p>
            </div>
            <Switch
              checked={formData.useEmergentKey}
              onCheckedChange={(v) => setFormData({ ...formData, useEmergentKey: v })}
              data-testid="emergent-key-toggle"
            />
          </div>
          
          {/* Progress */}
          {loading && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>{analyzing ? "Analyzing codebase..." : "Creating project..."}</span>
                <span>{progress}%</span>
              </div>
              <Progress value={progress} />
            </div>
          )}
          
          {/* Submit Button */}
          <Button 
            className="w-full gap-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700" 
            size="lg"
            onClick={handleSubmit}
            disabled={loading}
            data-testid="analyze-project-btn"
          >
            {loading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                {analyzing ? "Analyzing..." : "Creating..."}
              </>
            ) : (
              <>
                <Rocket className="h-5 w-5" />
                Analyze Project
              </>
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

// Project Detail Page
const ProjectDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState("analysis");
  const [reanalyzing, setReanalyzing] = useState(false);
  
  useEffect(() => {
    fetchProject();
  }, [id]);
  
  const fetchProject = async () => {
    try {
      const res = await axios.get(`${API}/projects/${id}`);
      setProject(res.data);
      // Auto-select tab based on status
      if (res.data.status === "docs_generated") {
        setActiveTab("docs");
      } else if (res.data.status === "plans_generated") {
        setActiveTab("plans");
      }
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
      const res = await axios.post(`${API}/projects/${id}/generate`, {
        projectId: id,
        generateType: type
      });
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
      const res = await axios.post(`${API}/projects/${id}/analyze`);
      setProject(res.data);
      toast.success("Re-analysis complete!");
    } catch (e) {
      toast.error("Re-analysis failed");
    } finally {
      setReanalyzing(false);
    }
  };
  
  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard`);
  };
  
  const exportAsZip = async () => {
    if (!project?.docs) return;
    
    const zip = new JSZip();
    const docs = project.docs;
    const name = project.name || "project";
    
    zip.file("README.md", docs.readme || "");
    const docsFolder = zip.folder("docs");
    docsFolder.file("user-guide.md", docs.userGuide || "");
    docsFolder.file("frontend-guide.md", docs.frontendGuide || "");
    docsFolder.file("backend-guide.md", docs.backendGuide || "");
    docsFolder.file("deployment-guide.md", docs.deploymentGuide || "");
    
    // Add deployment scripts
    if (project.deploymentPlans?.dockerPlan) {
      const scriptsFolder = zip.folder("scripts");
      scriptsFolder.file("docker-deployment.md", project.deploymentPlans.dockerPlan);
      scriptsFolder.file("vm-deployment.md", project.deploymentPlans.vmPlan || "");
      scriptsFolder.file("serverless-deployment.md", project.deploymentPlans.serverlessPlan || "");
    }
    
    const content = await zip.generateAsync({ type: "blob" });
    saveAs(content, `${name}-deployment-docs.zip`);
    toast.success("ZIP exported successfully!");
  };
  
  if (loading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }
  
  if (!project) return null;
  
  const { detectedTechStack, buildSteps, configFiles, envVars, deploymentPlans, docs } = project;
  
  return (
    <div className="container max-w-6xl py-8 px-4 md:px-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate("/")} data-testid="back-btn">
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{project.name}</h1>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {project.sourceType === "github_url" ? (
                <><Github className="h-4 w-4" /> {project.sourceUrl}</>
              ) : project.sourceType === "upload" ? (
                <><Upload className="h-4 w-4" /> Uploaded ZIP</>
              ) : (
                <><FileText className="h-4 w-4" /> Text Description</>
              )}
            </div>
          </div>
        </div>
        <StatusBadge status={project.status} />
      </div>
      
      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="analysis" className="gap-2" data-testid="tab-analysis">
            <Settings className="h-4 w-4" />
            Analysis
          </TabsTrigger>
          <TabsTrigger value="plans" className="gap-2" data-testid="tab-plans">
            <Server className="h-4 w-4" />
            Deployment Plans
          </TabsTrigger>
          <TabsTrigger value="docs" className="gap-2" data-testid="tab-docs">
            <FileCode className="h-4 w-4" />
            Documentation
          </TabsTrigger>
        </TabsList>
        
        {/* Analysis Tab */}
        <TabsContent value="analysis">
          <div className="grid gap-6 md:grid-cols-2">
            {/* Tech Stack */}
            <Card data-testid="tech-stack-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Cpu className="h-5 w-5" />
                  Detected Tech Stack
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Frontend</span>
                  <Badge variant="secondary">{detectedTechStack?.frontend || "Not detected"}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Backend</span>
                  <Badge variant="secondary">{detectedTechStack?.backend || "Not detected"}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Database</span>
                  <Badge variant="secondary">{detectedTechStack?.database || "Not detected"}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Infrastructure</span>
                  <Badge variant="secondary">{detectedTechStack?.infra || "Not detected"}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Services</span>
                  <Badge variant="secondary">{detectedTechStack?.services || "Not detected"}</Badge>
                </div>
              </CardContent>
            </Card>
            
            {/* Build Steps */}
            <Card data-testid="build-steps-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Globe className="h-5 w-5" />
                  Build Steps
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="mb-1 text-sm text-muted-foreground">Frontend Build</p>
                  <code className="block rounded bg-secondary p-2 text-sm">
                    {buildSteps?.frontendBuild || "N/A"}
                  </code>
                </div>
                <div>
                  <p className="mb-1 text-sm text-muted-foreground">Backend Build</p>
                  <code className="block rounded bg-secondary p-2 text-sm">
                    {buildSteps?.backendBuild || "N/A"}
                  </code>
                </div>
              </CardContent>
            </Card>
            
            {/* Config Files */}
            <Card data-testid="config-files-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileCode className="h-5 w-5" />
                  Config Files Found
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {configFiles?.length > 0 ? (
                    configFiles.map((file) => (
                      <Badge key={file} variant="outline">{file}</Badge>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground">No config files detected</p>
                  )}
                </div>
              </CardContent>
            </Card>
            
            {/* Env Vars */}
            <Card data-testid="env-vars-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="h-5 w-5" />
                  Environment Variables
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {envVars?.length > 0 ? (
                    envVars.map((v) => (
                      <Badge key={v} variant="outline">{v}</Badge>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground">No env vars detected</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
          
          {/* Action Buttons */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
            <Button 
              variant="outline" 
              onClick={() => handleGenerate("plans")}
              disabled={generating}
              data-testid="generate-plans-btn"
            >
              <Server className="mr-2 h-4 w-4" />
              Generate Deployment Plans
            </Button>
            <Button 
              variant="outline"
              onClick={() => handleGenerate("docs")}
              disabled={generating}
              data-testid="generate-docs-btn"
            >
              <FileCode className="mr-2 h-4 w-4" />
              Generate Documentation
            </Button>
            <Button
              className="gap-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700"
              onClick={() => handleGenerate("both")}
              disabled={generating}
              data-testid="generate-both-btn"
            >
              {generating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Rocket className="h-4 w-4" />
              )}
              Generate Both (Recommended)
            </Button>
          </div>
          
          {/* Re-analyze Button */}
          <div className="mt-4 flex justify-center">
            <Button 
              variant="ghost" 
              size="sm"
              onClick={handleReanalyze}
              disabled={reanalyzing}
              data-testid="reanalyze-btn"
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${reanalyzing ? "animate-spin" : ""}`} />
              Re-analyze
            </Button>
          </div>
        </TabsContent>
        
        {/* Deployment Plans Tab */}
        <TabsContent value="plans">
          {!deploymentPlans?.genericPlan ? (
            <Card className="border-dashed" data-testid="no-plans">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Server className="mb-4 h-12 w-12 text-muted-foreground/50" />
                <p className="mb-4 text-muted-foreground">No deployment plans generated yet</p>
                <Button onClick={() => handleGenerate("plans")} disabled={generating}>
                  {generating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Generate Deployment Plans
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-6">
              {/* Plan Cards */}
              {[
                { key: "genericPlan", title: "Generic Plan", icon: Globe, desc: "Universal deployment steps" },
                { key: "dockerPlan", title: "Docker Plan", icon: Box, desc: "Containerized deployment" },
                { key: "vmPlan", title: "VM/Server Plan", icon: Server, desc: "Linux server deployment" },
                { key: "serverlessPlan", title: "Serverless/PaaS Plan", icon: Cloud, desc: "Cloud platform deployment" }
              ].map(({ key, title, icon: Icon, desc }) => (
                <Card key={key} data-testid={`plan-card-${key}`}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2">
                        <Icon className="h-5 w-5" />
                        {title}
                      </CardTitle>
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={() => copyToClipboard(deploymentPlans[key], title)}
                      >
                        <Copy className="mr-2 h-4 w-4" />
                        Copy
                      </Button>
                    </div>
                    <CardDescription>{desc}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[300px] rounded-lg border bg-secondary/30 p-4">
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        className="prose prose-sm dark:prose-invert max-w-none"
                      >
                        {deploymentPlans[key]}
                      </ReactMarkdown>
                    </ScrollArea>
                  </CardContent>
                </Card>
              ))}
              
              {/* Export Button */}
              <div className="flex justify-center">
                <Button onClick={exportAsZip} className="gap-2" data-testid="export-scripts-btn">
                  <Download className="h-4 w-4" />
                  Export Deployment Scripts
                </Button>
              </div>
            </div>
          )}
        </TabsContent>
        
        {/* Documentation Tab */}
        <TabsContent value="docs">
          {!docs?.readme ? (
            <Card className="border-dashed" data-testid="no-docs">
              <CardContent className="flex flex-col items-center justify-center py-12">
                <FileCode className="mb-4 h-12 w-12 text-muted-foreground/50" />
                <p className="mb-4 text-muted-foreground">No documentation generated yet</p>
                <Button onClick={() => handleGenerate("docs")} disabled={generating}>
                  {generating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Generate Documentation
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-6">
              {/* Doc Cards */}
              {[
                { key: "readme", title: "README.md", desc: "Project overview and quick start" },
                { key: "userGuide", title: "user-guide.md", desc: "End-user documentation" },
                { key: "frontendGuide", title: "frontend-guide.md", desc: "Frontend development guide" },
                { key: "backendGuide", title: "backend-guide.md", desc: "Backend development guide" },
                { key: "deploymentGuide", title: "deployment-guide.md", desc: "Deployment instructions" }
              ].map(({ key, title, desc }) => (
                <Card key={key} data-testid={`doc-card-${key}`}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2">
                        <FileCode className="h-5 w-5" />
                        {title}
                      </CardTitle>
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={() => copyToClipboard(docs[key], title)}
                      >
                        <Copy className="mr-2 h-4 w-4" />
                        Copy
                      </Button>
                    </div>
                    <CardDescription>{desc}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[300px] rounded-lg border bg-secondary/30 p-4">
                      <ReactMarkdown 
                        remarkPlugins={[remarkGfm]}
                        className="prose prose-sm dark:prose-invert max-w-none"
                      >
                        {docs[key]}
                      </ReactMarkdown>
                    </ScrollArea>
                  </CardContent>
                </Card>
              ))}
              
              {/* Export Buttons */}
              <div className="flex flex-wrap justify-center gap-4">
                <Button onClick={exportAsZip} className="gap-2" data-testid="export-zip-btn">
                  <Download className="h-4 w-4" />
                  Export as ZIP
                </Button>
              </div>
              
              {/* Repo Structure Preview */}
              <Card data-testid="repo-structure-card">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FolderTree className="h-5 w-5" />
                    Export Structure
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="rounded-lg bg-secondary p-4 text-sm">
{`/${project.name}/
├── README.md
├── docs/
│   ├── user-guide.md
│   ├── frontend-guide.md
│   ├── backend-guide.md
│   └── deployment-guide.md
└── scripts/
    ├── docker-deployment.md
    ├── vm-deployment.md
    └── serverless-deployment.md`}
                  </pre>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

// Main App
function App() {
  return (
    <ThemeProvider>
      <div className="min-h-screen bg-background">
        <BrowserRouter>
          <Header />
          <main>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/new" element={<InputProjectPage />} />
              <Route path="/project/:id" element={<ProjectDetailPage />} />
            </Routes>
          </main>
        </BrowserRouter>
        <Toaster position="bottom-right" richColors />
      </div>
    </ThemeProvider>
  );
}

export default App;
