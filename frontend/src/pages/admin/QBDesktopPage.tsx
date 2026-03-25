/**
 * QB Desktop Connection Management Page
 *
 * Features:
 * - Create/edit Desktop connections
 * - Download QWC file
 * - View sync queue
 * - Monitor connection health
 * - Manual sync triggers
 */

import { useState, useEffect } from 'react';
import { Plus, Download, RefreshCw, Activity, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/useToast';
import api from '@/lib/axios';

interface QBConnection {
  id: string;
  connection_type: 'desktop';
  company_name: string;
  qbwc_username: string;
  qb_desktop_version: string;
  last_qbwc_poll_at: string | null;
  is_active: boolean;
  created_at: string;
}

interface SyncJob {
  id: string;
  job_type: string;
  entity_type: string;
  entity_id: string | null;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  error_message: string | null;
}

interface ConnectionHealth {
  status: 'connected' | 'disconnected';
  last_poll_at: string | null;
  pending_requests: number;
  qb_version: string | null;
}

export default function QBDesktopPage() {
  const [connections, setConnections] = useState<QBConnection[]>([]);
  const [syncJobs, setSyncJobs] = useState<SyncJob[]>([]);
  const [health, setHealth] = useState<ConnectionHealth | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  // Form state
  const [formData, setFormData] = useState({
    company_name: '',
    qbwc_username: '',
    qbwc_password: '',
    qb_desktop_version: 'Enterprise 2024',
  });

  // Load connections on mount
  useEffect(() => {
    loadConnections();
    loadSyncQueue();
    loadHealth();

    // Refresh every 30 seconds
    const interval = setInterval(() => {
      loadSyncQueue();
      loadHealth();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const loadConnections = async () => {
    try {
      const response = await api.get('/integrations/quickbooks/desktop/connections');
      setConnections(response.data);
    } catch (error) {
      console.error('Failed to load connections:', error);
    }
  };

  const loadSyncQueue = async () => {
    try {
      const response = await api.get('/integrations/quickbooks/desktop/sync-queue', {
        params: { limit: 20 },
      });
      setSyncJobs(response.data);
    } catch (error) {
      console.error('Failed to load sync queue:', error);
    }
  };

  const loadHealth = async () => {
    try {
      const response = await api.get('/integrations/quickbooks/desktop/health');
      setHealth(response.data);
    } catch (error) {
      console.error('Failed to load health:', error);
    }
  };

  const handleCreateConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      await api.post('/integrations/quickbooks/desktop/connections', formData);
      toast({
        title: 'Success',
        description: 'Desktop connection created successfully',
      });
      setIsDialogOpen(false);
      loadConnections();
      setFormData({
        company_name: '',
        qbwc_username: '',
        qbwc_password: '',
        qb_desktop_version: 'Enterprise 2024',
      });
    } catch (error: any) {
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to create connection',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadQWC = async (connectionId: string) => {
    try {
      const response = await api.get(
        `/integrations/quickbooks/desktop/connections/${connectionId}/download-qwc`,
        { responseType: 'blob' }
      );

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'sitara-pos-qbwc.qwc');
      document.body.appendChild(link);
      link.click();
      link.remove();

      toast({
        title: 'Success',
        description: 'QWC file downloaded. Import it into QBWC client.',
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to download QWC file',
        variant: 'destructive',
      });
    }
  };

  const handleManualSync = async () => {
    try {
      await api.post('/integrations/quickbooks/desktop/sync/trigger');
      toast({
        title: 'Success',
        description: 'Manual sync triggered. QBWC will fetch on next poll.',
      });
      loadSyncQueue();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to trigger sync',
        variant: 'destructive',
      });
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
      pending: 'outline',
      processing: 'secondary',
      completed: 'default',
      failed: 'destructive',
    };

    return <Badge variant={variants[status] || 'outline'}>{status}</Badge>;
  };

  const getHealthIcon = () => {
    if (!health) return null;

    if (health.status === 'connected') {
      return <CheckCircle2 className="h-5 w-5 text-green-600" />;
    }
    return <AlertCircle className="h-5 w-5 text-amber-600" />;
  };

  const getTimeSince = (timestamp: string | null) => {
    if (!timestamp) return 'Never';

    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now.getTime() - then.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hr ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">QuickBooks Desktop</h1>
          <p className="text-muted-foreground mt-1">
            Manage QBWC connections and sync queue
          </p>
        </div>

        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              New Connection
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Desktop Connection</DialogTitle>
              <DialogDescription>
                Setup a new QuickBooks Desktop connection via QBWC
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreateConnection} className="space-y-4">
              <div>
                <Label htmlFor="company_name">Company Name</Label>
                <Input
                  id="company_name"
                  value={formData.company_name}
                  onChange={(e) =>
                    setFormData({ ...formData, company_name: e.target.value })
                  }
                  placeholder="My Restaurant"
                  required
                />
              </div>

              <div>
                <Label htmlFor="qbwc_username">QBWC Username</Label>
                <Input
                  id="qbwc_username"
                  value={formData.qbwc_username}
                  onChange={(e) =>
                    setFormData({ ...formData, qbwc_username: e.target.value })
                  }
                  placeholder="pos_admin"
                  required
                />
              </div>

              <div>
                <Label htmlFor="qbwc_password">QBWC Password</Label>
                <Input
                  id="qbwc_password"
                  type="password"
                  value={formData.qbwc_password}
                  onChange={(e) =>
                    setFormData({ ...formData, qbwc_password: e.target.value })
                  }
                  placeholder="Create a strong password"
                  required
                />
                <p className="text-sm text-muted-foreground mt-1">
                  Save this password - you'll need it when importing the QWC file
                </p>
              </div>

              <div>
                <Label htmlFor="qb_version">QB Desktop Version</Label>
                <Select
                  value={formData.qb_desktop_version}
                  onValueChange={(value) =>
                    setFormData({ ...formData, qb_desktop_version: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Enterprise 2024">Enterprise 2024</SelectItem>
                    <SelectItem value="Enterprise 2023">Enterprise 2023</SelectItem>
                    <SelectItem value="Premier 2024">Premier 2024</SelectItem>
                    <SelectItem value="Premier 2023">Premier 2023</SelectItem>
                    <SelectItem value="Pro 2024">Pro 2024</SelectItem>
                    <SelectItem value="Pro 2023">Pro 2023</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isLoading}>
                  {isLoading ? 'Creating...' : 'Create Connection'}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Connection Health */}
      {health && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {getHealthIcon()}
              Connection Health
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Status</p>
                <p className="text-2xl font-bold capitalize">{health.status}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Last Poll</p>
                <p className="text-2xl font-bold">{getTimeSince(health.last_poll_at)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Pending Requests</p>
                <p className="text-2xl font-bold">{health.pending_requests}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">QB Version</p>
                <p className="text-2xl font-bold">{health.qb_version || 'Unknown'}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Connections List */}
      <Card>
        <CardHeader>
          <CardTitle>Desktop Connections</CardTitle>
          <CardDescription>QBWC connections configured for this tenant</CardDescription>
        </CardHeader>
        <CardContent>
          {connections.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No connections configured. Click "New Connection" to get started.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Company Name</TableHead>
                  <TableHead>Username</TableHead>
                  <TableHead>QB Version</TableHead>
                  <TableHead>Last Poll</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {connections.map((conn) => (
                  <TableRow key={conn.id}>
                    <TableCell className="font-medium">{conn.company_name}</TableCell>
                    <TableCell>{conn.qbwc_username}</TableCell>
                    <TableCell>{conn.qb_desktop_version}</TableCell>
                    <TableCell>{getTimeSince(conn.last_qbwc_poll_at)}</TableCell>
                    <TableCell>
                      <Badge variant={conn.is_active ? 'default' : 'secondary'}>
                        {conn.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDownloadQWC(conn.id)}
                      >
                        <Download className="h-4 w-4 mr-1" />
                        QWC
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Sync Queue */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Sync Queue</CardTitle>
              <CardDescription>Recent QBXML sync jobs</CardDescription>
            </div>
            <Button onClick={handleManualSync} variant="outline">
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {syncJobs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No sync jobs yet. Create an order to see it queued here.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job Type</TableHead>
                  <TableHead>Entity</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Error</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {syncJobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="font-medium">
                      {job.job_type.replace(/_/g, ' ')}
                    </TableCell>
                    <TableCell>{job.entity_type}</TableCell>
                    <TableCell>{getStatusBadge(job.status)}</TableCell>
                    <TableCell>{getTimeSince(job.created_at)}</TableCell>
                    <TableCell className="max-w-xs truncate text-red-600">
                      {job.error_message || '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
