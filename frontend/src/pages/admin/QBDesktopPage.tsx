/**
 * QB Desktop Connection Management Page
 *
 * Features:
 * - Create Desktop connection
 * - Download QWC file
 * - View sync queue
 * - Monitor connection health
 */

import { useState, useEffect } from 'react';
import { Download, RefreshCw, AlertCircle, CheckCircle2, XCircle } from 'lucide-react';
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import api from '@/lib/axios';

interface QBConnectionStatus {
  is_connected: boolean;
  connection_type: string | null;
  company_name: string | null;
  connected_at: string | null;
  last_sync_at: string | null;
  last_sync_status: string | null;
  qbwc_username: string | null;
  qb_desktop_version: string | null;
  last_qbwc_poll_at: string | null;
}

interface SyncJob {
  id: string;
  job_type: string;
  entity_type: string;
  entity_id: string | null;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'dead_letter';
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
  retry_count: number;
}

interface SyncStats {
  total_synced: number;
  last_24h_synced: number;
  last_24h_failed: number;
  pending_jobs: number;
  failed_jobs: number;
  dead_letter_jobs: number;
  last_sync_at: string | null;
}

export default function QBDesktopPage() {
  const [connectionStatus, setConnectionStatus] = useState<QBConnectionStatus | null>(null);
  const [syncJobs, setSyncJobs] = useState<SyncJob[]>([]);
  const [syncStats, setSyncStats] = useState<SyncStats | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  // Form state
  const [formData, setFormData] = useState({
    company_name: '',
    password: '',
    qb_version: 'Enterprise 2024',
    company_file_path: '',
  });

  // Load connection status on mount
  useEffect(() => {
    loadStatus();
    loadSyncQueue();
    loadSyncStats();

    // Refresh every 30 seconds
    const interval = setInterval(() => {
      loadStatus();
      loadSyncQueue();
      loadSyncStats();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const loadStatus = async () => {
    try {
      const response = await api.get('/integrations/quickbooks/status');
      setConnectionStatus(response.data);
    } catch (error) {
      console.error('Failed to load status:', error);
    }
  };

  const loadSyncQueue = async () => {
    try {
      const response = await api.get('/integrations/quickbooks/sync/jobs', {
        params: { page_size: 20 },
      });
      setSyncJobs(response.data);
    } catch (error) {
      console.error('Failed to load sync queue:', error);
    }
  };

  const loadSyncStats = async () => {
    try {
      const response = await api.get('/integrations/quickbooks/sync/stats');
      setSyncStats(response.data);
    } catch (error) {
      console.error('Failed to load sync stats:', error);
    }
  };

  const handleCreateConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      await api.post('/integrations/quickbooks/desktop/connect', null, {
        params: {
          password: formData.password,
          company_name: formData.company_name,
          qb_version: formData.qb_version,
          company_file_path: formData.company_file_path || undefined,
        },
      });
      toast({
        title: 'Success',
        description: 'Desktop connection created. Download the QWC file below.',
      });
      setIsDialogOpen(false);
      loadStatus();
      setFormData({
        company_name: '',
        password: '',
        qb_version: 'Enterprise 2024',
        company_file_path: '',
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

  const handleDownloadQWC = async () => {
    try {
      const response = await api.get('/integrations/quickbooks/desktop/qwc', {
        responseType: 'blob',
      });

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

  const handleDisconnect = async () => {
    if (!confirm('Are you sure you want to disconnect QuickBooks Desktop?')) {
      return;
    }

    try {
      await api.post('/integrations/quickbooks/disconnect');
      toast({
        title: 'Success',
        description: 'QuickBooks Desktop disconnected',
      });
      loadStatus();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to disconnect',
        variant: 'destructive',
      });
    }
  };

  const handleManualSync = async () => {
    try {
      const response = await api.post('/integrations/quickbooks/sync', {
        sync_type: 'sync_orders',
      });
      toast({
        title: 'Success',
        description: `Queued ${response.data.jobs_created} sync jobs`,
      });
      loadSyncQueue();
      loadSyncStats();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to trigger sync',
        variant: 'destructive',
      });
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-gray-200 text-gray-800',
      processing: 'bg-blue-200 text-blue-800',
      completed: 'bg-green-200 text-green-800',
      failed: 'bg-red-200 text-red-800',
      dead_letter: 'bg-red-600 text-white',
    };

    return (
      <span className={`px-2 py-1 rounded text-xs font-medium ${colors[status] || colors.pending}`}>
        {status}
      </span>
    );
  };

  const getHealthIcon = () => {
    if (!connectionStatus) return <XCircle className="h-5 w-5 text-gray-400" />;
    if (connectionStatus.is_connected && connectionStatus.connection_type === 'desktop') {
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

  const isConnected = connectionStatus?.is_connected && connectionStatus.connection_type === 'desktop';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">QuickBooks Desktop</h1>
          <p className="text-muted-foreground mt-1">
            Manage QBWC connection and sync queue
          </p>
        </div>

        {!isConnected ? (
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button>Connect QuickBooks Desktop</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Connect QuickBooks Desktop</DialogTitle>
                <DialogDescription>
                  Create a QBWC connection to sync with QuickBooks Desktop
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
                    placeholder="My Restaurant Company"
                    required
                  />
                </div>

                <div>
                  <Label htmlFor="password">QBWC Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={formData.password}
                    onChange={(e) =>
                      setFormData({ ...formData, password: e.target.value })
                    }
                    placeholder="Create a strong password"
                    required
                  />
                  <p className="text-sm text-muted-foreground mt-1">
                    Save this password - you'll need it when importing the QWC file into QBWC
                  </p>
                </div>

                <div>
                  <Label htmlFor="qb_version">QB Desktop Version</Label>
                  <Select
                    id="qb_version"
                    value={formData.qb_version}
                    onChange={(e) =>
                      setFormData({ ...formData, qb_version: e.target.value })
                    }
                  >
                    <option value="Enterprise 2024">Enterprise 2024</option>
                    <option value="Enterprise 2023">Enterprise 2023</option>
                    <option value="Premier 2024">Premier 2024</option>
                    <option value="Premier 2023">Premier 2023</option>
                    <option value="Pro 2024">Pro 2024</option>
                    <option value="Pro 2023">Pro 2023</option>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="company_file_path">Company File Path (Optional)</Label>
                  <Input
                    id="company_file_path"
                    value={formData.company_file_path}
                    onChange={(e) =>
                      setFormData({ ...formData, company_file_path: e.target.value })
                    }
                    placeholder="C:\Path\To\CompanyFile.QBW"
                  />
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
        ) : (
          <Button variant="destructive" onClick={handleDisconnect}>
            Disconnect
          </Button>
        )}
      </div>

      {/* Connection Status Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {getHealthIcon()}
            Connection Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!isConnected ? (
            <div className="text-center py-8 text-muted-foreground">
              No Desktop connection configured. Click "Connect QuickBooks Desktop" to get started.
            </div>
          ) : (
            <div className="grid grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Company</p>
                <p className="text-2xl font-bold">{connectionStatus.company_name}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">QB Version</p>
                <p className="text-2xl font-bold">{connectionStatus.qb_desktop_version || 'Unknown'}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Last QBWC Poll</p>
                <p className="text-2xl font-bold">{getTimeSince(connectionStatus.last_qbwc_poll_at)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Last Sync</p>
                <p className="text-2xl font-bold">{getTimeSince(connectionStatus.last_sync_at)}</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Download QWC Card */}
      {isConnected && (
        <Card>
          <CardHeader>
            <CardTitle>QBWC Setup</CardTitle>
            <CardDescription>
              Download and import the QWC file into QuickBooks Web Connector
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start gap-4">
              <div className="flex-1">
                <h4 className="font-semibold mb-2">Setup Instructions:</h4>
                <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
                  <li>Download QBWC from <a href="https://qbwc.qbn.intuit.com/" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">Intuit</a></li>
                  <li>Install QBWC on the PC running QuickBooks Desktop</li>
                  <li>Click "Download QWC File" below</li>
                  <li>In QBWC, go to File → Add an Application</li>
                  <li>Select the downloaded .QWC file</li>
                  <li>Enter the password you set during connection creation</li>
                  <li>QBWC will automatically poll every 15 minutes</li>
                </ol>
              </div>
              <Button onClick={handleDownloadQWC}>
                <Download className="h-4 w-4 mr-2" />
                Download QWC File
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Sync Stats */}
      {isConnected && syncStats && (
        <Card>
          <CardHeader>
            <CardTitle>Sync Statistics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-6 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Total</p>
                <p className="text-2xl font-bold">{syncStats.total_synced}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Last 24h</p>
                <p className="text-2xl font-bold text-green-600">{syncStats.last_24h_synced}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Failed</p>
                <p className="text-2xl font-bold text-red-600">{syncStats.last_24h_failed}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Pending</p>
                <p className="text-2xl font-bold text-amber-600">{syncStats.pending_jobs}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Failed</p>
                <p className="text-2xl font-bold text-red-600">{syncStats.failed_jobs}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Dead</p>
                <p className="text-2xl font-bold text-red-800">{syncStats.dead_letter_jobs}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Sync Queue */}
      {isConnected && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Sync Queue</CardTitle>
                <CardDescription>Recent QBXML sync jobs</CardDescription>
              </div>
              <Button onClick={handleManualSync} variant="outline">
                <RefreshCw className="h-4 w-4 mr-2" />
                Trigger Sync
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {syncJobs.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No sync jobs yet. Complete an order to see it queued here.
              </div>
            ) : (
              <div className="space-y-2">
                {syncJobs.map((job) => (
                  <div key={job.id} className="border rounded-lg p-4 flex items-center justify-between">
                    <div className="flex-1">
                      <p className="font-medium">{job.job_type.replace(/_/g, ' ')}</p>
                      <p className="text-sm text-muted-foreground">{job.entity_type}</p>
                    </div>
                    <div className="flex items-center gap-4">
                      {getStatusBadge(job.status)}
                      <span className="text-sm text-muted-foreground">{getTimeSince(job.created_at)}</span>
                      {job.retry_count > 0 && (
                        <span className="text-sm text-amber-600">Retries: {job.retry_count}</span>
                      )}
                    </div>
                    {job.error_message && (
                      <p className="text-sm text-red-600 mt-2 truncate max-w-md">{job.error_message}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
