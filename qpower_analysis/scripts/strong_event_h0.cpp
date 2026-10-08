// Exact H0 of a periodic isotropic lattice subset under pairwise Euclidean distance.
// No background vertex is inserted. Offsets are processed in squared-distance order.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

using U = uint32_t;
using Clock = std::chrono::steady_clock;

struct DSU {
    std::vector<U> parent, size;
    uint64_t count, ge10=0, ge100=0, ge1000=0, squared_sizes;
    U largest_root=1, largest_size=1;
    explicit DSU(U n): parent(uint64_t(n)+1), size(uint64_t(n)+1, 1), count(n), squared_sizes(n) {
        std::iota(parent.begin(), parent.end(), U(0));
        size[0]=0;
    }
    U find(U i) {
        while (parent[i] != i) {
            parent[i] = parent[parent[i]];
            i = parent[i];
        }
        return i;
    }
    bool join(U a, U b) {
        a=find(a); b=find(b);
        if (a==b) return false;
        if (size[a]<size[b]) std::swap(a,b);
        U sa=size[a], sb=size[b], sc=sa+sb;
        ge10 += int(sc>=10)-int(sa>=10)-int(sb>=10);
        ge100 += int(sc>=100)-int(sa>=100)-int(sb>=100);
        ge1000 += int(sc>=1000)-int(sa>=1000)-int(sb>=1000);
        squared_sizes += 2*uint64_t(sa)*sb;
        parent[b]=a; size[a]=sc; --count;
        if (sc>=largest_size) {largest_size=sc; largest_root=a;}
        return true;
    }
};

struct Offset {int z,y,x; U r2;};

int wrap(int p, int n) {
    if (p<0) p+=n;
    else if (p>=n) p-=n;
    return p;
}

std::vector<Offset> offsets(int radius, int nz, int ny, int nx, U after) {
    std::vector<Offset> result;
    const uint64_t r2=uint64_t(radius)*radius;
    // Use each minimum-image displacement once; even-size antipodes use -n/2.
    for (int z=-std::min(radius,nz/2); z<=std::min(radius,(nz-1)/2); ++z)
        for (int y=-std::min(radius,ny/2); y<=std::min(radius,(ny-1)/2); ++y)
            for (int x=-std::min(radius,nx/2); x<=std::min(radius,(nx-1)/2); ++x) {
                uint64_t d2=int64_t(z)*z+int64_t(y)*y+int64_t(x)*x;
                if (d2>after && d2<=r2) result.push_back({z,y,x,U(d2)});
            }
    std::sort(result.begin(),result.end(),[](const Offset& a,const Offset& b) {
        if (a.r2!=b.r2) return a.r2<b.r2;
        if (a.z!=b.z) return a.z<b.z;
        if (a.y!=b.y) return a.y<b.y;
        return a.x<b.x;
    });
    return result;
}

int main(int argc, char** argv) {
    try {
        if (argc!=7) throw std::runtime_error("Usage: engine packed_mask nz ny nx output_dir initial_radius");
        const std::string mask_path=argv[1], out=argv[5];
        const int nz=std::stoi(argv[2]), ny=std::stoi(argv[3]), nx=std::stoi(argv[4]);
        int radius=std::stoi(argv[6]);
        uint64_t cells=uint64_t(nz)*ny*nx;
        if (std::min({nz,ny,nx})<2 || cells>=UINT32_MAX || cells%8 || radius<1)
            throw std::runtime_error("Invalid dimensions or radius");
        if (std::filesystem::file_size(mask_path)!=(cells/8)) throw std::runtime_error("Packed mask size mismatch");
        std::filesystem::create_directories(out);
        auto started=Clock::now();
        auto seconds=[&](){return std::chrono::duration<double>(Clock::now()-started).count();};
        std::vector<uint8_t> packed(cells/8);
        std::ifstream input(mask_path,std::ios::binary);
        input.read(reinterpret_cast<char*>(packed.data()),packed.size());
        if (!input) throw std::runtime_error("Could not read mask");
        uint64_t total=0;
        for (uint8_t b:packed) total+=__builtin_popcount(unsigned(b));
        if (total==0 || total>=UINT32_MAX) throw std::runtime_error("Invalid selected point count");
        U n=U(total);
        std::cout<<"Exact graph: "<<n<<" selected vertices; allocating lattice lookup"<<std::endl;
        std::vector<U> grid(cells,0), positions;
        positions.reserve(n);
        U id=0;
        for (uint64_t byte=0;byte<packed.size();++byte) {
            unsigned bits=packed[byte];
            while (bits) {
                unsigned b=__builtin_ctz(bits);
                U p=U(byte*8+b);
                grid[p]=++id; positions.push_back(p);
                bits&=bits-1;
            }
        }
        std::vector<uint8_t>().swap(packed);
        DSU dsu(n);
        std::ofstream curve(out+"/connectivity_grid.csv");
        curve<<"r_squared_grid,r_grid,structure_count,merges_at_r,largest_size,largest_fraction,count_ge10,count_ge100,count_ge1000,effective_structure_count\n";
        curve<<std::setprecision(17);
        auto record=[&](U r2,uint64_t previous) {
            curve<<r2<<','<<std::sqrt(double(r2))<<','<<dsu.count<<','<<previous-dsu.count<<','
                 <<dsu.largest_size<<','<<double(dsu.largest_size)/n<<','<<dsu.ge10<<','<<dsu.ge100<<','
                 <<dsu.ge1000<<','<<double(n)*n/dsu.squared_sizes<<'\n';
            curve.flush();
            std::cout<<"r/dx="<<std::sqrt(double(r2))<<" N="<<dsu.count<<" largest="
                     <<double(dsu.largest_size)/n<<" elapsed="<<seconds()<<"s"<<std::endl;
        };
        const U plane=U(ny)*nx;
        int stride=std::max(1,std::max({nz,ny,nx})/128);
        std::vector<U> display;
        for (U i=1;i<=n;++i) {
            U p=positions[i-1];
            if ((p%nx)%stride==0 && ((p/nx)%ny)%stride==0 && (p/plane)%stride==0) display.push_back(i);
        }
        std::ofstream manifest(out+"/snapshot_manifest.csv");
        manifest<<"r_squared_grid,r_grid,structure_count,display_stride,display_points\n";
        auto snapshot=[&](U r2) {
            std::string stem="_r2_"+std::to_string(r2)+".csv";
            std::ofstream sample(out+"/sample"+stem);
            sample<<"point_id,z_grid,y_grid,x_grid,component_id,component_size\n";
            for (U i:display) {
                U p=positions[i-1], root=dsu.find(i);
                sample<<i<<','<<p/plane<<','<<(p/nx)%ny<<','<<p%nx<<','<<root<<','<<dsu.size[root]<<'\n';
            }
            std::map<U,uint64_t> size_counts;
            for (U i=1;i<=n;++i) if (dsu.parent[i]==i) ++size_counts[dsu.size[i]];
            std::ofstream sizes(out+"/sizes"+stem);
            sizes<<"component_size,number_of_components\n";
            uint64_t check_n=0,check_c=0;
            for (auto kv:size_counts) {
                sizes<<kv.first<<','<<kv.second<<'\n';
                check_n+=uint64_t(kv.first)*kv.second;check_c+=kv.second;
            }
            if (check_n!=n || check_c!=dsu.count) throw std::runtime_error("Snapshot size conservation failed");
            manifest<<r2<<','<<std::sqrt(double(r2))<<','<<dsu.count<<','<<stride<<','<<display.size()<<'\n';
            manifest.flush();
        };
        record(0,n);
        uint64_t previous=dsu.count;
        // All axis-adjacent edges. Positive directions suffice for this initial full scan.
        for (U i=1;i<=n;++i) {
            U p=positions[i-1], z=p/plane, y=(p/nx)%ny, x=p%nx;
            U qx=(x+1<U(nx))?p+1:p-(nx-1);
            U qy=(y+1<U(ny))?p+nx:p-U(ny-1)*nx;
            U qz=(z+1<U(nz))?p+plane:p-U(nz-1)*plane;
            if (grid[qx]) dsu.join(i,grid[qx]);
            if (grid[qy]) dsu.join(i,grid[qy]);
            if (grid[qz]) dsu.join(i,grid[qz]);
        }
        if (n>1) {record(1,previous); snapshot(1);}
        else snapshot(0);
        U last_r2=n>1?1:0;
        U anchor=dsu.find(dsu.largest_root);
        std::vector<U> active;
        active.reserve(n-dsu.largest_size);
        for (U i=1;i<=n;++i) if (dsu.find(i)!=anchor) active.push_back(i);
        const int max_radius=int(std::ceil(std::sqrt(double((int64_t(nz/2)*(nz/2))+
                                            int64_t(ny/2)*(ny/2)+int64_t(nx/2)*(nx/2)))));
        radius=std::min(radius,max_radius);
        while (dsu.count>1) {
            auto directions=offsets(radius,nz,ny,nx,last_r2);
            std::cout<<"Enumerated "<<directions.size()<<" offsets through r/dx="<<radius
                     <<"; active outside largest="<<active.size()<<std::endl;
            for (size_t first=0;first<directions.size() && dsu.count>1;) {
                U r2=directions[first].r2;
                size_t end=first+1;
                while (end<directions.size() && directions[end].r2==r2) ++end;
                previous=dsu.count;
                // Every inter-component edge has an endpoint outside the anchor component.
                // Both displacement signs are present, so scanning these endpoints is exact.
                for (U i:active) {
                    if (dsu.find(i)==dsu.find(anchor)) continue;
                    U p=positions[i-1];
                    int z=p/plane, y=(p/nx)%ny, x=p%nx;
                    for (size_t k=first;k<end;++k) {
                        const auto& d=directions[k];
                        U target=U(wrap(z+d.z,nz))*plane+U(wrap(y+d.y,ny))*nx+wrap(x+d.x,nx);
                        U j=grid[target];
                        if (j && dsu.join(i,j) && dsu.find(i)==dsu.find(anchor)) break;
                    }
                }
                record(r2,previous);
                bool crossing=(previous>100 && dsu.count<=100) || (previous>10 && dsu.count<=10);
                if (r2==2 || r2==3 || r2==4 || r2==16 || r2==64 || r2==256 || r2==1024 || crossing || dsu.count==1)
                    snapshot(r2);
                U old_root=dsu.find(anchor), new_root=dsu.find(dsu.largest_root);
                if (new_root!=old_root) {
                    active.clear();
                    for (U i=1;i<=n;++i) if (dsu.find(i)!=new_root) active.push_back(i);
                } else {
                    size_t write=0;
                    for (U i:active) if (dsu.find(i)!=new_root) active[write++]=i;
                    active.resize(write);
                }
                anchor=new_root; last_r2=r2; first=end;
            }
            if (dsu.count==1) break;
            if (radius==max_radius) throw std::runtime_error("Did not connect at torus diameter");
            radius=std::min(max_radius,std::max(radius+1,radius*2));
        }
        std::ofstream summary(out+"/engine_summary.json");
        summary<<std::setprecision(17)<<"{\n  \"selected_count\": "<<n
               <<",\n  \"final_structure_count\": "<<dsu.count
               <<",\n  \"connectivity_r_squared_grid\": "<<last_r2
               <<",\n  \"connectivity_r_grid\": "<<std::sqrt(double(last_r2))
               <<",\n  \"finite_h0_bars\": "<<n-1
               <<",\n  \"essential_h0_bars\": 1,\n  \"display_stride\": "<<stride
               <<",\n  \"display_points\": "<<display.size()
               <<",\n  \"elapsed_seconds\": "<<seconds()<<"\n}\n";
        std::cout<<"Completed exact H0: all selected points connected at r/dx="<<std::sqrt(double(last_r2))<<std::endl;
    } catch (const std::exception& e) {
        std::cerr<<e.what()<<std::endl;
        return 1;
    }
    return 0;
}
