# vigos.ghdash — gh-dash PR/issue dashboard (#824). Parameterized port: the
# hardcoded personal repo filters became `repoFilters`; the CPU-tuning
# lessons (lean scoped sections, capped closed lists) are the defaults.
# Reuses the gh login; the gh-dash package rides this module (not devTools).
#
# Per-project scope and section profiles (#1586): `gh-dash-repo [profile]`
# launches the dashboard scoped to the repo of the directory it starts in —
# derived from `origin`, not declared, so nothing lands in project repos —
# and `profiles` names alternative section sets for projects whose workflow
# differs (sections are the one key gh-dash replaces rather than merges).
# A profile may hold one list per view (#1595): PR and issue queues are not
# filtered alike, and a PR-shaped filter is a dead section under Issues.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.vigos.ghdash;

  scope = if cfg.repoFilters == [ ] then "involves:@me" else lib.concatStringsSep " " cfg.repoFilters;

  # The generated section set, parameterized over the scope so the same three
  # sections serve both the global settings (real scope, bare `gh-dash`
  # unchanged) and the wrapper's `default` template (placeholder scope).
  mkSections = scope': [
    {
      title = "Involved";
      filters = "is:open involves:@me ${scope'}";
    }
    {
      title = "Open";
      filters = "is:open ${scope'}";
    }
    {
      title = "Recently closed";
      filters = "is:closed ${scope'} sort:updated-desc";
      limit = 10;
    }
  ];

  sections = mkSections scope;

  # gh-dash has no template variable for "the current repo", so the wrapper
  # substitutes this token at launch time (sed over the rendered template).
  placeholder = "__GH_DASH_SCOPE__";

  # Profile authors write scope-free filters; the module appends the
  # placeholder — the same composition the generated sections use — so a
  # profile cannot silently ship unscoped (the idle-CPU cost the tuning
  # defaults exist to prevent).
  profileSections = map (
    s:
    {
      inherit (s) title;
      filters = "${s.filters} ${placeholder}";
    }
    // lib.optionalAttrs (s.limit != null) { inherit (s) limit; }
  );

  # The issues view of the `default` template. The module only mkDefaults
  # `programs.gh-dash.settings.issuesSections`, so anything else is the
  # consumer's own dashboard: pass it through verbatim rather than replace it
  # (#1595). Such a section already carries the scope its author chose — one
  # that wants to follow the launch repo writes the placeholder itself.
  defaultIssueSections =
    if config.programs.gh-dash.settings.issuesSections == sections then
      mkSections placeholder
    else
      config.programs.gh-dash.settings.issuesSections;

  # Every wrapper-selectable template, each a { prSections; issuesSections; }
  # pair — PR and issue queues are not filtered alike, so a profile that names
  # only one list mirrors it and one that names both keeps them apart (#1595).
  # `default` mirrors the generated sections, so `gh-dash-repo` is valid with
  # no profiles declared — and, as with vigos.sesh layout profiles, it always
  # wins over a same-named key.
  profileTemplates =
    lib.mapAttrs (_: p: {
      prSections = profileSections p.prSections;
      issuesSections = profileSections (
        if p.issuesSections == null then p.prSections else p.issuesSections
      );
    }) cfg.profiles
    // {
      default = {
        prSections = mkSections placeholder;
        issuesSections = defaultIssueSections;
      };
    };

  # A template is the FULL merged settings with only the section keys
  # swapped, so consumer tuning (refetch interval, limits, layout) carries
  # into every per-repo config. Rendered as JSON — a subset of YAML, which
  # gh-dash reads fine — so the file text is eval-pure and assertable in
  # tests (a yaml generator would need a build).
  templateText = template: builtins.toJSON (config.programs.gh-dash.settings // template);

  # Launch gh-dash scoped to the repo of the current directory:
  #   gh-dash-repo [profile]
  # Repo comes from `origin` at the launch CWD; outside a GitHub repo the
  # scope falls back to `repoFilters` (or involves:@me), so the config is
  # always valid. The rendered config lives at a deterministic runtime path,
  # overwritten each launch — no cleanup, and `exec` is safe.
  ghDashRepo = pkgs.writeShellApplication {
    name = "gh-dash-repo";
    runtimeInputs = with pkgs; [
      git
      gnused
      gh-dash
      coreutils
      findutils
    ];
    text = ''
      profile="''${1:-default}"
      profiles_dir="''${XDG_CONFIG_HOME:-$HOME/.config}/gh-dash/profiles"
      src="$profiles_dir/$profile.yml"
      if [ ! -f "$src" ]; then
        printf 'gh-dash-repo: unknown profile %s\nValid profiles:%s\n' \
          "$profile" "$(find "$profiles_dir" -name '*.yml' -printf ' %f' | sed 's/\.yml//g')" >&2
        exit 1
      fi

      url=$(git config --get remote.origin.url 2>/dev/null || true)
      slug=""
      case "$url" in
        *github.com*)
          slug=$(printf '%s' "$url" | sed -E 's#^git@[^:]+:##; s#^https?://[^/]+/##; s#\.git$##')
          ;;
      esac
      if [ -n "$slug" ]; then
        sub="repo:$slug"
      else
        sub=${lib.escapeShellArg scope}
      fi

      dir="''${XDG_RUNTIME_DIR:-/tmp}/gh-dash"
      mkdir -p "$dir"
      conf="$dir/''${slug//\//-}-$profile.yml"
      sed "s#${placeholder}#$sub#g" "$src" > "$conf"
      exec gh-dash --config "$conf"
    '';
  };

  sectionModule = lib.types.submodule {
    options = {
      title = lib.mkOption {
        type = lib.types.str;
        description = "Section title shown in the dashboard.";
      };
      filters = lib.mkOption {
        type = lib.types.str;
        example = "is:open review-requested:@me";
        description = ''
          GitHub search filters, WITHOUT a repo/scope qualifier — the module
          appends the launch-time scope, exactly as the generated sections
          compose theirs.
        '';
      };
      limit = lib.mkOption {
        type = lib.types.nullOr lib.types.int;
        default = null;
        description = "Per-section row cap (null = gh-dash's default).";
      };
    };
  };

  sectionList = lib.types.listOf sectionModule;

  # A profile is one dashboard, so it stays one entry — but PR and issue
  # queues take different filters, so it may name a list per view. A bare list
  # coerces to "both views, same sections", which is what every profile
  # written before #1595 means. The source type is shape-only (coercedTo
  # forbids submodules there); the entries are checked by `prSections` once
  # coerced, so a malformed section still fails at eval.
  profileType = lib.types.coercedTo (lib.types.listOf lib.types.anything) (l: { prSections = l; }) (
    lib.types.submodule {
      options = {
        prSections = lib.mkOption {
          type = sectionList;
          description = "Sections for the pull-request view.";
        };
        issuesSections = lib.mkOption {
          type = lib.types.nullOr sectionList;
          default = null;
          description = ''
            Sections for the issues view; null mirrors {option}`prSections`.
            Set it when the two queues differ — a PR filter like
            `review-requested:@me` is a permanently empty issues section —
            and to `[ ]` to leave the issues view empty rather than wrong.
          '';
        };
      };
    }
  );
in
{
  options.vigos.ghdash = {
    enable = lib.mkEnableOption "the gh-dash PR/issue dashboard";
    repoFilters = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [ "repo:vig-os/devcontainer" ];
      description = ''
        GitHub search scope for the generated sections (e.g. repo:/org:
        qualifiers). Empty = everything involving you. Scoping to the repos
        you work in keeps each idle dashboard cheap. Also the fallback scope
        `gh-dash-repo` uses outside a GitHub repo.
      '';
    };
    profiles = lib.mkOption {
      type = lib.types.attrsOf profileType;
      default = { };
      example = lib.literalExpression ''
        {
          solo = [
            {
              title = "Open";
              filters = "is:open";
            }
          ];
          shared = {
            prSections = [
              {
                title = "Needs my review";
                filters = "is:open review-requested:@me";
              }
              {
                title = "Open";
                filters = "is:open";
              }
            ];
            issuesSections = [
              {
                title = "Assigned to me";
                filters = "is:open assignee:@me";
              }
            ];
          };
        }
      '';
      description = ''
        Named section sets selected per launch (`gh-dash-repo <name>`), for
        projects whose workflow differs from the generated three sections —
        a team repo wants review queues a solo repo has no use for. Each
        profile is either a bare list (both views get those sections) or
        `{ prSections; issuesSections; }`, since the qualifiers that make a
        PR queue useful either do not apply to issues or mean something else.
        A {option}`vigos.sesh` layout profile can point its dashboard window
        at `gh-dash-repo <name>`, so selection rides the session entry that
        already identifies the project. The `default` profile is the
        generated section set and cannot be redefined here; its issues view
        keeps a consumer-set `programs.gh-dash.settings.issuesSections`
        instead of replacing it.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    programs.gh-dash = {
      enable = lib.mkDefault true;
      settings = {
        prSections = lib.mkDefault sections;
        issuesSections = lib.mkDefault sections;
        defaults.refetchIntervalMinutes = lib.mkDefault 10;
      };
    };

    home = {
      packages = [ ghDashRepo ];
      file = lib.mapAttrs' (
        name: template:
        lib.nameValuePair ".config/gh-dash/profiles/${name}.yml" { text = templateText template; }
      ) profileTemplates;
    };
  };
}
