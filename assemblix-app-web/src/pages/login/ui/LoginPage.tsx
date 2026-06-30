import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
import { useLoginMutation, OAuthButtons } from "@/entities/session";
import { clearWorkspace } from "@/entities/organization";
import { baseApi } from "@/shared/api";
import { toast } from "sonner";

export const LoginPage = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [login, { isLoading }] = useLoginMutation();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { t } = useTranslation();

  const formSchema = z.object({
    email: z.string().email({
      message: t("auth.emailValidation"),
    }),
    password: z.string().min(3, {
      message: t("auth.passwordMinLength"),
    }),
  });

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  async function onSubmit(values: z.infer<typeof formSchema>) {
    try {
      // Сбрасываем workspace и кеш перед логином для чистого состояния
      dispatch(clearWorkspace());
      dispatch(baseApi.util.resetApiState());

      await login(values).unwrap();
      navigate("/");
    } catch (error) {
      console.error(error);
      toast.error(t("auth.loginError"), {
        description: t("auth.invalidCredentials"),
      });
    }
  }

  return (
    <div>
      <div className="flex flex-col space-y-1 mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {t("auth.login")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("auth.enterCredentials")}</p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
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
                    placeholder="your@email.com"
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
                <div className="flex items-center justify-between">
                  <FormLabel className="text-foreground">
                    {t("auth.password")}
                  </FormLabel>
                  <Link
                    to="/forgot-password"
                    className="text-sm font-medium text-primary hover:underline underline-offset-4"
                  >
                    {t("auth.forgotPassword")}
                  </Link>
                </div>
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

          <div className="pt-2">
            <Button
              type="submit"
              disabled={isLoading}
              className="w-full h-11 shadow-lg shadow-primary/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
            >
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t("auth.signIn")}
            </Button>
          </div>
        </form>
      </Form>

      {/* OAuth кнопки */}
      <OAuthButtons />
    </div>
  );
};
