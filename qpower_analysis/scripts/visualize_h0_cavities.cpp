#include <algorithm>
#include <array>
#include <cstdint>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <unordered_map>
#include <vector>
using U=uint32_t;
using XYZ=std::array<int,3>;
// Foreground: 6 neighbors; complement: 26 neighbors, avoiding diagonal false cavities.
int main(int argc,char**argv){try{
 if(argc!=4) throw std::runtime_error("mask n output-directory");
 int n=std::stoi(argv[2]); U plane=U(n)*n; uint64_t total=uint64_t(n)*plane;
 if(total>=UINT32_MAX || n%8) throw std::runtime_error("invalid grid");
 std::string out=argv[3]; std::filesystem::create_directories(out);
 std::vector<uint8_t> a(total); std::ifstream in(argv[1],std::ios::binary);
 for(uint64_t j=0;j<total/8;++j){char b;in.get(b);if(!in)throw std::runtime_error("short mask");for(int k=0;k<8;++k)a[j*8+k]=(uint8_t(b)>>k)&1;}
 auto neighbor=[&](U p,int dz,int dy,int dx){int z=p/plane,y=(p/n)%n,x=p%n; z=(z+dz+n)%n;y=(y+dy+n)%n;x=(x+dx+n)%n;return U(z)*plane+U(y)*n+x;};
 std::array<XYZ,6> axis={XYZ{1,0,0},XYZ{-1,0,0},XYZ{0,1,0},XYZ{0,-1,0},XYZ{0,0,1},XYZ{0,0,-1}};
 std::vector<std::vector<U>> top;
 uint64_t selected=0,components=0;
 for(uint64_t p=0;p<total;++p)if(a[p]==1){
  std::vector<U> q{U(p)};a[p]=2;
  for(size_t j=0;j<q.size();++j)for(auto d:axis){U v=neighbor(q[j],d[0],d[1],d[2]);if(a[v]==1){a[v]=2;q.push_back(v);}}
  ++components;selected+=q.size();
  if(top.size()<3 || q.size()>top.back().size()){top.push_back(std::move(q));std::sort(top.begin(),top.end(),[](auto&x,auto&y){return x.size()>y.size();});if(top.size()>3)top.pop_back();}
 }
 std::cout<<"selected="<<selected<<" components="<<components<<std::endl;
 for(size_t k=0;k<top.size();++k){for(U p:top[k])a[p]=3+k;std::cout<<"rank="<<k+1<<" size="<<top[k].size()<<std::endl;}
 std::ofstream stats(out+"/statistics.csv");stats<<"rank,structure_points,exterior_points,cavity_count,green_points,red_points,wrapping_background_components\n";
 for(size_t rank=0;rank<top.size();++rank){
  int target=3+rank;
  // Save exact foreground positions; rendering may aggregate these later.
  std::ofstream fg(out+"/blue_"+std::to_string(rank+1)+".bin",std::ios::binary);
  fg.write(reinterpret_cast<char*>(top[rank].data()),top[rank].size()*sizeof(U));fg.close();
  for(auto&v:a)v&=63;
  U seed=0;while(a[seed]==target)++seed;
  std::deque<U> q;q.push_back(seed);a[seed]|=128;uint64_t ext=0;
  while(!q.empty()){
   U p=q.front();q.pop_front();++ext;
   int z=p/plane,y=(p/n)%n,x=p%n;
   for(int dz=-1;dz<=1;++dz)for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx){
    if(!(dz||dy||dx))continue;
    int zz=z+dz,yy=y+dy,xx=x+dx;if(zz<0)zz+=n;else if(zz>=n)zz-=n;if(yy<0)yy+=n;else if(yy>=n)yy-=n;if(xx<0)xx+=n;else if(xx>=n)xx-=n;
    U v=U(zz)*plane+U(yy)*n+xx;
    if(!(a[v]&128) && (a[v]&63)!=target){a[v]|=128;q.push_back(v);}
   }
  }
  if(ext<=total/2)throw std::runtime_error("Chosen exterior is not a verified majority component; choose a different seed");
  std::ofstream green(out+"/green_"+std::to_string(rank+1)+".bin",std::ios::binary),red(out+"/red_"+std::to_string(rank+1)+".bin",std::ios::binary);
  uint64_t ng=0,nr=0,nc=0,nwrap=0;
  for(uint64_t p=0;p<total;++p)if(!(a[p]&128) && (a[p]&63)!=target){
   std::vector<U> pts{U(p)};std::unordered_map<U,XYZ> lift;lift[U(p)]={0,0,0};a[p]|=128;bool winding=false;
   for(size_t j=0;j<pts.size();++j){U u=pts[j];XYZ base=lift.at(u);
    for(int dz=-1;dz<=1;++dz)for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx){if(!(dz||dy||dx))continue;U v=neighbor(u,dz,dy,dx);if((a[v]&63)==target)continue;
     XYZ xyz{base[0]+dz,base[1]+dy,base[2]+dx};
     if(!(a[v]&128)){a[v]|=128;pts.push_back(v);lift.emplace(v,xyz);}else{auto it=lift.find(v);if(it!=lift.end()&&it->second!=xyz)winding=true;}
    }
   }
   if(winding){++nwrap;continue;}++nc;
   for(U v:pts){if(a[v]&63){green.write(reinterpret_cast<char*>(&v),sizeof(v));++ng;}else{red.write(reinterpret_cast<char*>(&v),sizeof(v));++nr;}}
  }
  stats<<rank+1<<','<<top[rank].size()<<','<<ext<<','<<nc<<','<<ng<<','<<nr<<','<<nwrap<<'\n';stats.flush();
  std::cout<<"rank="<<rank+1<<" cavities="<<nc<<" green="<<ng<<" red="<<nr<<" exterior="<<ext<<std::endl;
 }
 }catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}}
