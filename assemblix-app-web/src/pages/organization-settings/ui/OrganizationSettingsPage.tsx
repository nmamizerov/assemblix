import { useState } from "react";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
import {
  Loader2,
  Plus,
  Trash2,
  Users,
  Building2,
  Crown,
  CreditCard,
} from "lucide-react";
import { Button } from "@/shared/ui/button";
import { useFormatDate } from "@/shared/lib/format-date";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Pagination } from "@/shared/ui/pagination";
import {
  useGetOrganizationQuery,
  useUpdateOrganizationMutation,
  useGetOrganizationMembersQuery,
  useRemoveOrganizationMemberMutation,
  selectCurrentOrganizationId,
  type OrganizationMember,
} from "@/entities/organization";
import {
  useGetBillingUsageQuery,
  useGetTransactionsQuery,
  PlanBadge,
  UsageProgressCard,
  LimitWarningBanner,
  CreditsBalanceCard,
  CreditsTransactionsList,
  calculateUsageStatus,
} from "@/entities/billing";
import { useMeQuery } from "@/entities/session";
import { AddMemberModal } from "./AddMemberModal";
import { DeleteMemberDialog } from "./DeleteMemberDialog";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

const TRANSACTIONS_PER_PAGE = 10;

export const OrganizationSettingsPage = () => {
  const { t } = useTranslation();
  const { formatLongDate } = useFormatDate();
  const navigate = useNavigate();
  const currentOrganizationId = useSelector(selectCurrentOrganizationId);
  const { data: currentUser } = useMeQuery();

  const { data: organization, isLoading: isLoadingOrg } =
    useGetOrganizationQuery(currentOrganizationId!, {
      skip: !currentOrganizationId,
    });

  const { data: members, isLoading: isLoadingMembers } =
    useGetOrganizationMembersQuery(
      { organizationId: currentOrganizationId!, skip: 0, limit: 100 },
      { skip: !currentOrganizationId }
    );

  const { data: billingUsage } = useGetBillingUsageQuery(undefined, {
    skip: !currentOrganizationId,
  });

  const [transactionsPage, setTransactionsPage] = useState(1);

  const { data: transactions } = useGetTransactionsQuery(
    {
      skip: (transactionsPage - 1) * TRANSACTIONS_PER_PAGE,
      limit: TRANSACTIONS_PER_PAGE,
    },
    { skip: !currentOrganizationId }
  );

  const totalTransactionPages = transactions
    ? Math.ceil(transactions.total / TRANSACTIONS_PER_PAGE)
    : 0;

  const [updateOrganization, { isLoading: isUpdating }] =
    useUpdateOrganizationMutation();
  const [removeMember, { isLoading: isDeleting }] =
    useRemoveOrganizationMemberMutation();

  const [orgName, setOrgName] = useState("");
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedMember, setSelectedMember] =
    useState<OrganizationMember | null>(null);

  // Синхронизация названия организации с сервера
  const displayOrgName = orgName || organization?.name || "";

  // Проверка, является ли текущий пользователь владельцем
  const isOwner =
    organization && currentUser && organization.ownerId === currentUser.id;

  const handleUpdateName = async () => {
    if (!currentOrganizationId || !displayOrgName.trim()) {
      toast.error(t("organization.enterOrganizationName"));
      return;
    }

    if (displayOrgName.trim() === organization?.name) {
      toast.info(t("organization.nameNotChanged"));
      return;
    }

    try {
      await updateOrganization({
        organizationId: currentOrganizationId,
        data: { name: displayOrgName.trim() },
      }).unwrap();
      toast.success(t("organization.nameUpdated"));
      setOrgName(""); // Сбрасываем локальное состояние после успешного обновления
    } catch (error) {
      console.error(error);
      toast.error(t("organization.nameUpdateError"));
    }
  };

  const handleDeleteClick = (member: OrganizationMember) => {
    setSelectedMember(member);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!selectedMember || !currentOrganizationId) return;

    try {
      await removeMember({
        organizationId: currentOrganizationId,
        userId: selectedMember.id,
      }).unwrap();
      toast.success(t("organization.removeMemberModal.removeSuccess"));
      setDeleteDialogOpen(false);
      setSelectedMember(null);
    } catch (error) {
      console.error(error);
      const err = error as { status?: number };
      if (err?.status === 400) {
        toast.error(t("organization.removeMemberModal.cannotRemoveOwner"));
      } else if (err?.status === 403) {
        toast.error(t("organization.removeMemberModal.noPermission"));
      } else {
        toast.error(t("organization.removeMemberModal.removeError"));
      }
    }
  };

  const formatDate = (dateString: string) => formatLongDate(dateString);

  if (isLoadingOrg || !organization) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-full">
      <main className="container mx-auto">
        <div className="mx-auto space-y-8">
          {/* Header */}
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              {t("organization.title")}
            </h1>
            <p className="mt-2 text-muted-foreground">
              {t("organization.subtitle")}
            </p>
          </div>

          {/* Organization Name Section */}
          <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <Building2 className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h2 className="text-xl font-semibold">
                  {t("organization.basicSettings")}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {t("organization.organizationInfo")}
                </p>
              </div>
            </div>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="org-name">
                  {t("organization.organizationName")}
                </Label>
                <div className="flex gap-2">
                  <Input
                    id="org-name"
                    value={displayOrgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    placeholder={t("organization.organizationName")}
                    disabled={!isOwner}
                  />
                  <Button
                    onClick={handleUpdateName}
                    disabled={
                      isUpdating ||
                      !isOwner ||
                      displayOrgName.trim() === organization.name
                    }
                  >
                    {isUpdating ? t("organization.saving") : t("common.save")}
                  </Button>
                </div>
                {!isOwner && (
                  <p className="text-sm text-muted-foreground">
                    {t("organization.onlyOwnerCanEdit")}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Billing Section */}
          {billingUsage && (
            <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
              <div className="mb-6 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                    <CreditCard className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold">
                      {t("billing.section.title")}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {t("billing.section.subtitle")}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <PlanBadge plan={billingUsage.plan} />
                  <Button
                    onClick={() => navigate("/pricing")}
                    variant="outline"
                  >
                    {t("billing.viewPlans")}
                  </Button>
                </div>
              </div>

              {/* Usage Stats */}
              <div className="grid gap-4 md:grid-cols-2">
                <UsageProgressCard
                  title={t("billing.usage.agents")}
                  current={billingUsage.usage.agents.current}
                  limit={billingUsage.usage.agents.limit}
                  icon={<Users className="h-5 w-5" />}
                />
                <CreditsBalanceCard
                  creditsBalance={billingUsage.credits?.creditsBalance ?? 0}
                  creditsPerMonth={billingUsage.credits?.creditsPerMonth ?? 0}
                  nextResetDate={billingUsage.credits?.nextResetDate ?? ""}
                />
              </div>

              {/* Warning Banners */}
              {(() => {
                const agentsStatus = calculateUsageStatus(
                  billingUsage.usage.agents.current,
                  billingUsage.usage.agents.limit
                );
                const creditsUsed =
                  (billingUsage.credits?.creditsPerMonth ?? 0) -
                  (billingUsage.credits?.creditsBalance ?? 0);
                const creditsStatus = calculateUsageStatus(
                  creditsUsed,
                  billingUsage.credits?.creditsPerMonth ?? 0
                );

                return (
                  <div className="mt-4 space-y-3">
                    {!agentsStatus.isUnlimited &&
                      agentsStatus.percentage >= 80 && (
                        <LimitWarningBanner
                          type="agents"
                          current={billingUsage.usage.agents.current}
                          limit={billingUsage.usage.agents.limit!}
                          percentage={agentsStatus.percentage}
                        />
                      )}
                    {creditsStatus.percentage >= 80 && (
                      <LimitWarningBanner
                        type="credits"
                        current={billingUsage.credits?.creditsBalance ?? 0}
                        limit={billingUsage.credits?.creditsPerMonth ?? 0}
                        percentage={creditsStatus.percentage}
                      />
                    )}
                  </div>
                );
              })()}

              {/* Transactions List */}
              {transactions && transactions.total > 0 && (
                <div className="mt-4">
                  <CreditsTransactionsList
                    transactions={transactions.data}
                    total={transactions.total}
                    footer={
                      <Pagination
                        currentPage={transactionsPage}
                        totalPages={totalTransactionPages}
                        onPageChange={setTransactionsPage}
                      />
                    }
                  />
                </div>
              )}
            </div>
          )}

          {/* Members Section */}
          <div className="rounded-lg border border-border bg-card shadow-sm">
            <div className="border-b border-border p-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                    <Users className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold">
                      {t("organization.members")}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {members?.length || 0}{" "}
                      {t("organization.membersCount", {
                        count: members?.length || 0,
                      })}
                    </p>
                  </div>
                </div>
                {isOwner && (
                  <Button
                    onClick={() => setAddModalOpen(true)}
                    size="lg"
                    className="shrink-0"
                  >
                    <Plus className="mr-2 h-5 w-5" />
                    {t("organization.addMember")}
                  </Button>
                )}
              </div>
            </div>

            {/* Members Table */}
            {isLoadingMembers ? (
              <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : !members || members?.length === 0 ? (
              <div className="flex min-h-[300px] flex-col items-center justify-center text-center p-6">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                  <Users className="h-8 w-8 text-primary" />
                </div>
                <h3 className="mt-4 text-lg font-semibold">
                  {t("organization.noMembers")}
                </h3>
                <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                  {t("organization.noMembersDescription")}
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b border-border bg-muted/50">
                    <tr>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("organization.member")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("organization.email")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("organization.role")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("organization.joinedDate")}
                      </th>
                      {isOwner && (
                        <th className="px-6 py-4 text-right text-sm font-semibold text-foreground">
                          {t("organization.actions")}
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {members.map((member) => (
                      <tr
                        key={member.id}
                        className="transition-colors hover:bg-muted/50"
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                              <Users className="h-4 w-4 text-primary" />
                            </div>
                            <span className="font-medium text-foreground">
                              {member.fullName || t("organization.noName")}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {member.email}
                        </td>
                        <td className="px-6 py-4">
                          {member.isOwner ? (
                            <div className="inline-flex items-center gap-1.5 rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning">
                              <Crown className="h-3 w-3" />
                              {t("organization.roles.owner")}
                            </div>
                          ) : (
                            <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                              {t("organization.roles.member")}
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {formatDate(member.joinedAt)}
                        </td>
                        {isOwner && (
                          <td className="px-6 py-4 text-right">
                            {!member.isOwner &&
                              member.id !== currentUser?.id && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => handleDeleteClick(member)}
                                  className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              )}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Modals */}
      {currentOrganizationId && (
        <>
          <AddMemberModal
            open={addModalOpen}
            onOpenChange={setAddModalOpen}
            organizationId={currentOrganizationId}
          />
          <DeleteMemberDialog
            open={deleteDialogOpen}
            onOpenChange={setDeleteDialogOpen}
            memberName={selectedMember?.fullName || ""}
            memberEmail={selectedMember?.email || ""}
            onConfirm={handleDeleteConfirm}
            isDeleting={isDeleting}
          />
        </>
      )}
    </div>
  );
};
