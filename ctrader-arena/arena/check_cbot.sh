#!/bin/bash
# Compile-check a cTrader cBot against the official cTrader.Automate NuGet API.  Usage: bash arena/check_cbot.sh agents/X/XBot.cs
set -e
D=$(mktemp -d); mkdir -p $D/src; cp "$1" $D/src/
cat > $D/check.csproj <<'P'
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net6.0</TargetFramework><Nullable>disable</Nullable><EnableDefaultCompileItems>false</EnableDefaultCompileItems><OutputType>Library</OutputType></PropertyGroup>
  <ItemGroup><PackageReference Include="cTrader.Automate" Version="*" /></ItemGroup>
  <ItemGroup><Compile Include="src/*.cs" /></ItemGroup>
</Project>
P
cd $D && dotnet build -nologo -v q 2>&1 | grep -E "error|warning CS|Build succeeded|Error" | sort -u | head -40
rm -rf $D
