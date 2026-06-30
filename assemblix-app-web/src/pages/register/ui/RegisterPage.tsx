import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useDispatch } from "react-redux";

import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/shared/ui/form";
import { useRegisterOrLoginMutation, OAuthButtons } from "@/entities/session";
import { clearWorkspace } from "@/entities/organization";
import { baseApi } from "@/shared/api";
import { toast } from "sonner";
import { getUtmForRegistration, clearUtmFromStorage } from "@/shared/lib/utm";

export const RegisterPage = () => {
  const { t } = useTranslation();
  const [showPassword, setShowPassword] = useState(false);
  const [accountFound, setAccountFound] = useState(false);
  const [oauthProvider, setOauthProvider] = useState<string | null>(null);
  const [registerOrLogin, { isLoading }] = useRegisterOrLoginMutation();
  const navigate = useNavigate();
  const dispatch = useDispatch();

  const formSchema = useMemo(
    () =>
      z
        .object({
          name: z.string().min(2, {
            message: t("auth.nameMinLength"),
          }),
          email: z.string().email({
            message: t("auth.emailValidation"),
          }),
          password: z.string().min(3, {
            message: t("auth.passwordMinLength"),
          }),
          confirmPassword: z.string().min(3, {
            message: t("auth.passwordMinLength"),
          }),
        })
        .refine((data) => data.password === data.confirmPassword, {
          message: t("auth.passwordsNotMatch"),
          path: ["confirmPassword"],
        }),
    [t]
  );

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
  });

  async function onSubmit(values: z.infer<typeof formSchema>) {
    try {
      // Сбрасываем workspace и кеш перед регистрацией для чистого состояния
      dispatch(clearWorkspace());
      dispatch(baseApi.util.resetApiState());

      const utmData = getUtmForRegistration();

      const result = await registerOrLogin({
        email: values.email,
        password: values.password,
        fullName: values.name,
        ...utmData,
      }).unwrap();

      switch (result.action) {
        case "registered":
        case "logged_in":
          clearUtmFromStorage();
          navigate("/");
          break;
        case "account_exists":
          setAccountFound(true);
          setOauthProvider(null);
          toast.error(t("auth.accountExists"), {
            description: t("auth.accountExistsDescription"),
          });
          break;
        case "oauth_account":
          setOauthProvider(result.provider);
          setAccountFound(false);
          toast.error(t("auth.oauthAccountExists"), {
            description: t("auth.oauthAccountExistsDescription", { provider: result.provider }),
          });
          break;
      }
    } catch (error) {
      console.error(error);
      toast.error(t("auth.registerError"), {
        description: t("auth.registerErrorDescription"),
      });
    }
  }

  return (
    <div>
      <div className="flex flex-col space-y-1 mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {t("auth.register")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("auth.registerDescription")}</p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-foreground">
                  {t("auth.name")}
                </FormLabel>
                <FormControl>
                  <Input
                    placeholder={t("auth.namePlaceholder")}
                    {...field}
                    className="h-11 bg-input/50 focus:bg-background transition-colors"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-foreground">
                  {t("auth.email")}
                </FormLabel>
                <FormControl>
                  <Input
                    placeholder={t("auth.emailPlaceholder")}
                    {...field}
                    className="h-11 bg-input/50 focus:bg-background transition-colors"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-foreground">
                  {t("auth.password")}
                </FormLabel>
                <FormControl>
                  <div className="relative">
                    <Input
                      type={showPassword ? "text" : "password"}
                      placeholder="••••••••"
                      {...field}
                      className="h-11 bg-input/50 focus:bg-background transition-colors pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {showPassword ? (
                        <EyeOff className="w-5 h-5" />
                      ) : (
                        <Eye className="w-5 h-5" />
                      )}
                    </button>
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="confirmPassword"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-foreground">
                  {t("auth.confirmPassword")}
                </FormLabel>
                <FormControl>
                  <Input
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    {...field}
                    className="h-11 bg-input/50 focus:bg-background transition-colors"
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {accountFound && (
            <p className="text-sm text-destructive">
              {t("auth.accountExists")}{" "}
              <a href="/login" className="underline font-medium">
                {t("auth.loginLink")}
              </a>
            </p>
          )}

          {oauthProvider && (
            <p className="text-sm text-destructive">
              {t("auth.oauthAccountExistsDescription", { provider: oauthProvider })}
            </p>
          )}

          <div className="pt-2">
            <Button
              type="submit"
              disabled={isLoading}
              className="w-full h-11 shadow-lg shadow-primary/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {accountFound ? t("auth.loginInstead") : t("auth.createAccount")}
            </Button>
          </div>
        </form>
      </Form>
      <OAuthButtons />
    </div>
  );
};
